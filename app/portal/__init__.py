from flask import Blueprint

portal_bp = Blueprint("portal", __name__, template_folder="../templates/portal")

from app.portal import routes
