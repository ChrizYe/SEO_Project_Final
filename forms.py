from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo



class RegistrationForm(FlaskForm):
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me') 
    submit = SubmitField('Login')

# class UpdateUsernameForm(FlaskForm):
#     username = StringField('New Username', validators=[DataRequired(), Length(min=2, max=20)])
#     current_password = PasswordField('Current Password', validators=[DataRequired()])
#     submit_username = SubmitField('Update Username')

# class UpdateEmailForm(FlaskForm):
#     email = StringField('New Email', validators=[DataRequired(), Email()])
#     current_password = PasswordField('Current Password', validators=[DataRequired()])
#     submit_email = SubmitField('Update Email')

# class ChangePasswordForm(FlaskForm):
#     current_password = PasswordField('Current Password', validators=[DataRequired()])
#     new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
#     confirm_new_password = PasswordField('Confirm New Password', validators=[
#         DataRequired(), EqualTo('new_password', message='Passwords must match')
#     ])
#     submit_password = SubmitField('Change Password')
