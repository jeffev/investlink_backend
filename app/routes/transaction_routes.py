from flask import request
from flask_jwt_extended import get_jwt_identity

from services.transaction_service import (
    create_transaction,
    delete_transaction,
    list_transactions,
)


def list_transactions_json():
    user_id = get_jwt_identity()
    return list_transactions(user_id)


def create_transaction_json():
    user_id = get_jwt_identity()
    data = request.get_json()
    return create_transaction(user_id, data)


def delete_transaction_json(transaction_id):
    user_id = get_jwt_identity()
    return delete_transaction(user_id, transaction_id)
