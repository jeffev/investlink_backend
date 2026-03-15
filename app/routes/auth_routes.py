from datetime import timedelta

from flask import jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required


@jwt_required(refresh=True)
def refresh_token_json():
    identity = get_jwt_identity()
    access_token = create_access_token(
        identity=identity, expires_delta=timedelta(hours=3)
    )
    return jsonify({"access_token": access_token}), 200
