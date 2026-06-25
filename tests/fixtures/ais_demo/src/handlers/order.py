def get_order(cursor, order_id):
    # VIOLATION: raw SQL in a handler, bypassing the repository layer.
    return cursor.execute("SELECT * FROM orders WHERE id = ?", [order_id])
