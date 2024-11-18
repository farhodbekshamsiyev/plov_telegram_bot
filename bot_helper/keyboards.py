from django.contrib.auth import get_user_model
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from apps.inventory.models import Category, Product

User = get_user_model()


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
    categories: Category = Category.objects.only("id", "name")
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
        products = Product.objects.filter(category__id=category_id, is_active=True).values('id', 'name')
        print(products)

        buttons = [InlineKeyboardButton(product["name"], callback_data=f'food_{product["id"]}') for product in products]
        buttons.append(InlineKeyboardButton("🔝Back to Menu", callback_data='back_menu'))
        keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select an item:", reply_markup=reply_markup)
