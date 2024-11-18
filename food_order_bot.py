import asyncio
import os
import sys
from datetime import datetime
from os.path import join, dirname
from typing import List

import django
from django.db.models import Subquery

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ptb.settings')
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

django.setup()

from bot_helper.keyboards import show_main_menu, show_menu, show_category

from dotenv import load_dotenv

from django.contrib.auth import get_user_model
from apps.inventory.models import Product, Category
from apps.order.models import Order, OrderItem, StatusType, PredefinedLocations
from handler import get_total_price

User = get_user_model()

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
TOKEN = os.getenv('TELEGRAM_TOKEN')

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)


# @sync_to_async
# def get_all_users():
#     return User.objects.all()


# @sync_to_async
# def get_all_categories():
#     return Category.objects.all()


async def show_food_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    food_id = str(query.data.split('_')[-1])
    product_details: Product = Product.objects.filter(id=food_id, is_active=True).first()

    if not product_details:
        await query.edit_message_text("Product not found.")
        return

    count = context.user_data.get(f'count_{food_id}', 1)

    keyboard = [
        [InlineKeyboardButton("Add to Cart", callback_data=f'add_to_{food_id}')],
        [InlineKeyboardButton("➖", callback_data=f'decrement_{food_id}'),
         InlineKeyboardButton(str(count), callback_data='item_count'),
         InlineKeyboardButton("➕", callback_data=f'increment_{food_id}')],
        [InlineKeyboardButton("🔝Back to Category",
                              callback_data=f'back_category_{product_details.category.first().id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # query.data["back_menu"] = keyboard[-1][0]
    print(keyboard[-1][0].callback_data)
    photo = product_details.image

    await query.message.reply_photo(
        photo=photo,
        caption=f'The {product_details.name}\nPrice: {product_details.price} per {product_details.type.lower()}',
        reply_markup=reply_markup
    )


async def change_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, sign=None) -> None:
    query = update.callback_query
    await query.answer()

    food_id = str(query.data.split('_')[-1])
    count = context.user_data.get(f'count_{food_id}', 1)

    match sign:
        case "+":
            count += 1
        case "-":
            if count <= 1:
                return
            count -= 1
        case _:
            return

    context.user_data[f'count_{food_id}'] = count

    await update_item_quantity(query, context, food_id, count)


async def update_item_quantity(query, context, food_id, count) -> None:
    category = Category.objects.filter(
        product__id=food_id, product__is_active=True
    ).only("name").first()

    # food = Product.objects.filter(id=food_id, is_active=True).first()

    keyboard = [
        [InlineKeyboardButton("Add to Cart", callback_data=f'add_to_{food_id}')],
        [InlineKeyboardButton("➖", callback_data=f'decrement_{food_id}'),
         InlineKeyboardButton(str(count), callback_data='item_count'),
         InlineKeyboardButton("➕", callback_data=f'increment_{food_id}')],
        [InlineKeyboardButton("🔝Back to Category", callback_data=f'back_category_{category}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_reply_markup(reply_markup=reply_markup)


async def change_order_item_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE, sign=None):
    query = update.callback_query
    await query.answer()

    item_id = str(query.data.split('_')[-1])
    item: OrderItem = OrderItem.objects.get(id=item_id)

    match sign:
        case "+":
            item.quantity += 1
        case "-" | "del":
            item.quantity -= 1
        case _:
            return
    item.save()

    if item.quantity < 1 or sign == "del":
        item.delete()

    cart_items = OrderItem.objects.filter(order=item.order).all()
    if not cart_items.exists():
        return await asyncio.gather(query.delete_message(), query.from_user.send_message(f"Your cart is empty."))

    message, reply_markup = renderer(cart_items)

    await query.edit_message_text(text=message, reply_markup=reply_markup)


async def item_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()


async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = update.callback_query.from_user
    telegram_id = user.id

    try:
        db_user = User.objects.get(telegram_id=telegram_id)
    except User.DoesNotExist:
        await query.edit_message_text("User not found.")
        return

    food_id = str(query.data.split('_')[-1])
    product: Product = Product.objects.get(id=food_id)

    # Retrieve or create an order for the user
    order, created = Order.objects.get_or_create(user=db_user, status=StatusType.PENDING)

    # Check if the product is already in the order
    order_item, item_created = OrderItem.objects.get_or_create(order=order, product=product)
    # OrderItem.objects.filter(
    #     order__user=db_user,
    #     order__status=StatusType.PENDING,
    #     product__id=food_id
    # ).select_related('product', 'order')

    if not item_created:
        # Update quantity if the item already exists
        order_item.quantity += context.user_data.get(f'count_{food_id}', 1)
    else:
        # Set initial quantity if it's a new item
        order_item.quantity = context.user_data.get(f'count_{food_id}', 1)

    order_item.save()

    # await query.answer(f"Added {product.name} to your cart.")
    cart_items = OrderItem.objects.filter(order=order).all()
    message, total_price = get_total_price(cart_items=cart_items)
    await query.delete_message()
    await query.from_user.send_message(f"Added {product.name} to your cart.\nTotal price: {total_price:.2f}")


def renderer(cart_items: List[OrderItem]) -> (str, InlineKeyboardMarkup):
    message = "📥Your cart:\n\n"
    total_price = 0
    keyboards = []
    for counter, item in enumerate(cart_items):
        product = item.product
        message += f"{counter + 1}. {product.name}\n \
            By {product.type}: {item.quantity} x ${product.price} = ${(item.quantity * product.price):.02}\n\n"
        total_price += item.quantity * product.price

        keyboards.append(
            [InlineKeyboardButton(f"❌ {counter + 1}. {product.name}", callback_data=f'remove_{item.id}')], )
        keyboards.append(
            [InlineKeyboardButton("➖", callback_data=f'subtract_order_{item.id}'),
             InlineKeyboardButton(str(item.quantity), callback_data='item_count'),
             InlineKeyboardButton("➕", callback_data=f'add_order_{item.id}')],
        )

    keyboards.append(
        [InlineKeyboardButton(f"Check out ✅", callback_data=f'checkout_{cart_items[0].order.id}')]
    )

    reply_markup = InlineKeyboardMarkup(keyboards)

    message += f"\nTotal: ${total_price:.02}"

    return message, reply_markup


def render_orders(cart_items: List[OrderItem], **kwargs):
    checking_out = kwargs.get('checking_out', False)
    if checking_out:
        pass
        # print(cart_items)
    message = "📥Your orders:\n\n"
    for counter, item in enumerate(cart_items):
        total_price = 0
        order_datetime = str(item.order.updated_at)
        date_time_obj = datetime.fromisoformat(order_datetime)
        iso_format_date = date_time_obj.strftime('%B %d, %Y at %I:%M %p')
        product = item.product
        message += f"on {iso_format_date}:\n"
        message += f"{counter + 1}. {product.name}\n \
            By {product.type}: {item.quantity} x ${product.price} = ${(item.quantity * product.price):.02}\n"

        total_price += item.quantity * product.price
        message += f"\nTotal: ${total_price:.02}\n\n"

    return message


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = str(query.data.split('_')[-1])
    order = Order.objects.get(id=order_id)

    keyboard = [
        [InlineKeyboardButton("Predefined Locations", callback_data=f'predefined_location_{order.id}')],
        [InlineKeyboardButton("Share Location", callback_data=f'share_location_{order.id}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Please select a delivery option:", reply_markup=reply_markup)


async def show_predefined_locations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = str(query.data.split('_')[-1])
    locations = list(PredefinedLocations.objects.values_list('location_name', 'location_code'))

    keyboard = [
        [InlineKeyboardButton(
            location[0],
            callback_data=f"select_location_{order_id}_{location[1]}"
        )] for location in locations
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Select a delivery location:", reply_markup=reply_markup)


async def request_user_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "Please share your location:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Share Location", request_location=True)]],
                                         one_time_keyboard=True, resize_keyboard=True)
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE, **kwargs) -> None:
    is_predefined = kwargs.get('is_predefined', False)
    if is_predefined:
        query = update.callback_query
        user = query.from_user

        code = query.data.split('_')[-1]
        location = PredefinedLocations.objects.get(location_code=code)
    else:
        location = update.message.location
        user = update.message.from_user

    # Save location to the order
    order = Order.objects.filter(user__telegram_id=user.id, status=StatusType.PENDING).first()
    order.location = f"{location.latitude},{location.longitude}"
    order.save()

    # Ask for the phone number
    await query.message.reply_text(
        "Please share your phone number:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Share Phone Number", request_contact=True)]],
                                         one_time_keyboard=True, resize_keyboard=True)
    )


async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    phone_number = update.message.contact.phone_number
    user = update.message.from_user

    # Save phone number to the user profile
    db_user = User.objects.get(telegram_id=user.id)
    db_user.phone_number = phone_number
    db_user.save()

    # Update the order status
    order = Order.objects.filter(user=db_user, status=StatusType.PENDING).first()
    order.status = StatusType.IN_PROGRESS
    order.save()

    await update.message.reply_text("Thank you! Your order has been placed and is now in progress.")

    await checkout_and_send_order(update, context, order=order)

    await show_main_menu(update, context)


GROUP_CHAT_ID = "@orderplov"


async def checkout_and_send_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order):
    user = update.message.from_user

    user_telegram_id = user.id

    cart_order: Order = Order.objects.prefetch_related('items').filter(user__telegram_id=user_telegram_id,
                                                                       status__in=[StatusType.IN_PROGRESS]).first()
    cart_items = cart_order.items.all()

    cart_order.status = StatusType.CHECKED_OUT

    message = render_orders(cart_items, checking_out=True)

    # Send order details to the group
    await context.bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=message,
    )

    # Send the location to the group (replace with actual location data)
    latitude, longitude = cart_order.location.split(",")

    await context.bot.send_location(
        chat_id=GROUP_CHAT_ID,
        latitude=latitude,
        longitude=longitude
    )

    cart_order.save()

    # Notify user of successful checkout
    # await update.message.reply_text("Your order has been placed and sent to the kitchen!")


def get_user(user_telegram_id: int) -> User:
    return User.objects.get(telegram_id=user_telegram_id)


def get_cart_order(user_id, status=StatusType.PENDING):
    return Order.objects.filter(user=user_id, status__in=[status]).first()


def get_cart_items(cart_order):
    return OrderItem.objects.select_related("product").filter(order=cart_order).all()


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("User not found.")
        return

    cart_order = get_cart_order(user)
    if not cart_order:
        await update.message.reply_text("Your cart is empty.")
        return

    cart_items = get_cart_items(cart_order)
    if not cart_items.exists():
        await update.message.reply_text("Your cart is empty.")
        return

    message, reply_markup = renderer(cart_items)

    await update.message.reply_text(message, reply_markup=reply_markup)


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_telegram_id = update.effective_user.id
    try:
        user = User.objects.get(telegram_id=user_telegram_id)
    except User.DoesNotExist:
        await update.message.reply_text("User not found.")
        return

    cart_order = Order.objects.filter(
        user=user,
        status__in=[StatusType.IN_PROGRESS, StatusType.COMPLETED]
    ).first()
    if not cart_order:
        await update.message.reply_text("You have no orders yet.")
        return

    cart_items = OrderItem.objects.filter(order=cart_order).all()
    if not cart_items.exists():
        await update.message.reply_text("You have no orders yet.")
        return

    message = render_orders(cart_items)

    await update.message.reply_text(message)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.data.startswith('menu_'):
        await show_category(update, context)
    elif query.data.startswith('food_'):
        await show_food_detail(update, context)
    elif query.data == 'back_menu':
        await show_menu(update, context)
    elif query.data.startswith('back_category_'):
        await show_category(update, context, True)
    elif query.data.startswith('add_to_'):
        await add_to_cart(update, context)
    elif query.data.startswith('increment_'):
        await change_item_quantity(update, context, "+")
    elif query.data.startswith('decrement_'):
        await change_item_quantity(update, context, "-")
    elif query.data.startswith('add_order_'):
        await change_order_item_quantity(update, context, "+")
    elif query.data.startswith('subtract_'):
        await change_order_item_quantity(update, context, "-")
    elif query.data.startswith('remove_'):
        await change_order_item_quantity(update, context, "del")
    elif query.data == 'item_count':
        await item_count(update, context)
    elif query.data.startswith('checkout_'):
        await start_checkout(update, context)
    elif query.data.startswith('predefined_location_'):
        await show_predefined_locations(update, context)
    elif query.data.startswith('share_location_'):
        await request_user_location(update, context)
    elif query.data.startswith('select_location_'):
        await handle_location(update, context, is_predefined=True)
    elif update.message.location:
        await handle_location(update, context)
    elif update.message.contact:
        await handle_phone_number(update, context)


def main() -> None:
    application = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()
    # add BotCommand

    application.add_handler(CommandHandler("start", show_main_menu))
    application.add_handler(MessageHandler(filters.Regex('^Menu$'), show_menu))
    application.add_handler(MessageHandler(filters.Regex('^Orders$'), show_orders))
    application.add_handler(MessageHandler(filters.Regex('^Show Cart$'), show_cart))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.CONTACT, handle_phone_number))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == '__main__':
    main()
