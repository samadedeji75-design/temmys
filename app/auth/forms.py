from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email


class EmailLoginForm(FlaskForm):
    """Used by both Admin and Teacher login — same shape, different table.
    CSRF is validated globally via the X-CSRFToken header (see base.js),
    not a hidden form field, since these submit as JSON."""
    class Meta:
        csrf = False

    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")


class PortalLoginForm(FlaskForm):
    """Parent/Student portal login — admission number, not email or name."""
    class Meta:
        csrf = False

    admission_number = StringField("Admission Number", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")
