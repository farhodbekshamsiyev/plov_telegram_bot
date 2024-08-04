import asyncio
import os
import sys
from os.path import join, dirname
from pathlib import Path
from typing import List

import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ptb.settings')
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')
django.setup()

from dotenv import load_dotenv
from django.contrib.auth import get_user_model
from apps.inventory.models import Category, Product
from apps.order.models import Order, OrderItem, StatusType
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

from asgiref.sync import sync_to_async


@sync_to_async
def get_all_users():
    return User.objects.all()


# @sync_to_async
# def get_all_categories():
#     return Category.objects.all()


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user if update.message else update.callback_query.from_user

    User.objects.get_or_create(username=user.username, telegram_id=user.id)

    keyboard = [
        [KeyboardButton("Menu")],
        [KeyboardButton("Orders")],
        [KeyboardButton("Show Cart")],
        [KeyboardButton("Leave Feedback")]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if update.message:
        await update.message.reply_text(f"Welcome {user.first_name}! Please choose an option:",
                                        reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("Welcome! Please choose an option:", reply_markup=reply_markup)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    categories = Category.objects.all()
    print(categories)

    keyboard = [
        [InlineKeyboardButton(category.name.capitalize(), callback_data=f'menu_{category.id}')
         for category in categories]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("Menu:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Menu:", reply_markup=reply_markup)


async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE, delete=False) -> None:
    if delete:
        await update.callback_query.delete_message()
    else:
        query = update.callback_query
        await query.answer()

        category_id = str(query.data.split('_')[-1])
        products = Product.objects.filter(category__id=category_id, is_active=True)

        keyboard = [[InlineKeyboardButton(product.name, callback_data=f'food_{product.id}') for product in products],
                    [InlineKeyboardButton("🔝Back to Menu", callback_data='back_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select an item:", reply_markup=reply_markup)


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


async def increment_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    food_id = str(query.data.split('_')[-1])
    count = context.user_data.get(f'count_{food_id}', 1)
    count += 1
    context.user_data[f'count_{food_id}'] = count

    await update_quantity_button(query, context, food_id, count)


async def decrement_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    food_id = str(query.data.split('_')[-1])
    count = context.user_data.get(f'count_{food_id}', 1)
    if count > 1:
        count -= 1
    else:
        return
    context.user_data[f'count_{food_id}'] = count

    await update_quantity_button(query, context, food_id, count)


async def update_quantity_button(query, context, food_id, count) -> None:
    food = Product.objects.filter(id=food_id, is_active=True).first()

    keyboard = [
        [InlineKeyboardButton("Add to Cart", callback_data=f'add_to_{food_id}')],
        [InlineKeyboardButton("➖", callback_data=f'decrement_{food_id}'),
         InlineKeyboardButton(str(count), callback_data='item_count'),
         InlineKeyboardButton("➕", callback_data=f'increment_{food_id}')],
        [InlineKeyboardButton("🔝Back to Category", callback_data=f'back_category_{food.category}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_reply_markup(reply_markup=reply_markup)


async def add_order_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    item_id = str(query.data.split('_')[-1])
    item: OrderItem = OrderItem.objects.get(id=item_id)
    item.quantity += 1
    item.save()

    cart_items = OrderItem.objects.filter(order=item.order).all()
    if not cart_items.exists():
        await update.message.reply_text("Your cart is empty.")
        return

    message, reply_markup = renderer(cart_items)

    await query.edit_message_text(text=message, reply_markup=reply_markup)


async def subtract_order_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    item_id = str(query.data.split('_')[-1])
    item = OrderItem.objects.get(id=item_id)

    if item.quantity > 1:
        item.quantity -= 1
        item.save()
    else:
        item.delete()

    cart_items = OrderItem.objects.filter(order=item.order).all()
    if not cart_items.exists():
        await query.delete_message()
        await query.from_user.send_message(f"Your cart is empty.")
        return

    message, reply_markup = renderer(cart_items)

    await query.edit_message_text(text=message, reply_markup=reply_markup)


async def remove_order_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item_id = str(query.data.split('_')[-1])
    item = OrderItem.objects.get(id=item_id)
    item.delete()

    cart_items = OrderItem.objects.filter(order=item.order).all()
    if not cart_items.exists():
        return await asyncio.gather(query.delete_message(), query.from_user.send_message(f"Your cart is empty."))
        # await update.message.reply_text("Your cart is empty.")

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
    product = Product.objects.get(id=food_id)

    # Retrieve or create an order for the user
    order, created = Order.objects.get_or_create(user=db_user, status=StatusType.PENDING)

    # Check if the product is already in the order
    order_item, item_created = OrderItem.objects.get_or_create(order=order, product=product)

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
    # await update.message.reply_text(f"Added {product.name} to your cart.")
    # await bot.send_message(chat_id=telegram_id, text=f"Added {product.name} to the cart.")


def renderer(cart_items: List[OrderItem]) -> (str, InlineKeyboardMarkup):
    message = "📥Your cart:\n\n"
    total_price = 0
    keyboards = []
    for counter, item in enumerate(cart_items):
        product = item.product
        message += f"{counter + 1}. {product.name}\n \
            By {product.type}: {item.quantity} x ${product.price} = {item.quantity * product.price}\n\n"
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

    message += f"\nTotal: ${total_price}"

    return message, reply_markup


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_telegram_id = update.effective_user.id
    try:
        user = User.objects.get(telegram_id=user_telegram_id)
    except User.DoesNotExist:
        await update.message.reply_text("User not found.")
        return

    cart_order = Order.objects.filter(user=user, status=StatusType.PENDING).first()
    if not cart_order:
        await update.message.reply_text("Your cart is empty.")
        return

    cart_items = OrderItem.objects.filter(order=cart_order).all()
    if not cart_items.exists():
        await update.message.reply_text("Your cart is empty.")
        return

    message, reply_markup = renderer(cart_items)

    await update.message.reply_text(message, reply_markup=reply_markup)


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
        await increment_quantity(update, context)
    elif query.data.startswith('decrement_'):
        await decrement_quantity(update, context)
    elif query.data.startswith('add_order_'):
        await add_order_item(update, context)
    elif query.data.startswith('subtract_'):
        await subtract_order_item(update, context)
    elif query.data.startswith('remove_'):
        await remove_order_item(update, context)
    elif query.data == 'item_count':
        await item_count(update, context)


def main() -> None:
    application = Application.builder().token(TOKEN).read_timeout(30).write_timeout(30).build()

    application.add_handler(CommandHandler("start", show_main_menu))
    application.add_handler(MessageHandler(filters.Regex('^Menu$'), show_menu))
    application.add_handler(MessageHandler(filters.Regex('^Orders$'), show_menu))
    application.add_handler(MessageHandler(filters.Regex('^Show Cart$'), show_cart))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == '__main__':
    main()
