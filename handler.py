from apps.order.models import OrderItem


def get_total_price(cart_items: list):
    message = "Your cart:\n"
    total_price = 0
    for item in cart_items:
        product = item.product
        message += f"{product.name} - {item.quantity} {product.type} - ${item.quantity * product.price}\n"
        total_price += item.quantity * product.price

    return message, total_price
