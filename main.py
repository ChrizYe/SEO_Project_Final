import os
from dotenv import load_dotenv
import git
import math

from flask import Flask, render_template, url_for, flash, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_behind_proxy import FlaskBehindProxy
from sqlalchemy import Text
import json


from werkzeug.security import generate_password_hash, check_password_hash

from forms import RegistrationForm, LoginForm,UpdateUsernameForm,UpdateEmailForm,ChangePasswordForm
from newsapi import NewsApiClient
import google.generativeai as genai


def configure():
    load_dotenv()


configure()
saved_latest_articles = []
saved_latest_summaries = ["Empty" for i in range(50)]

saved_top_articles = []
saved_top_summaries = ["Empty" for i in range(7)]


NEWS_API_KEY = os.getenv("NEWS_API_KEY")
if not NEWS_API_KEY:
    raise ValueError("Missing `NEWS_API_KEY` in .env file")

newsapi = NewsApiClient(api_key=NEWS_API_KEY)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Missing `GEMINI_API_KEY` in .env file")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")  

# Init Flask app and extensions
app = Flask(__name__)
proxied = FlaskBehindProxy(app)  # Enable proxy support

app.config['SECRET_KEY'] = 'd002cde69ced4dfd3544654676af1df8'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)


# Database structure
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    favorites = db.Column(Text, nullable=False, default="[]")

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

with app.app_context():
    db.create_all()


@app.route("/", methods=['GET', 'POST'])
@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():

        # Check for available email registration
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            form.email.errors.append("This email is already registered.")
            return render_template('register.html', title='Register', form=form)
        
        # Check for available username registration
        existing_username = User.query.filter_by(username=form.username.data).first()
        if existing_username:
            form.username.errors.append("That username is already taken.")
            return render_template('register.html', title='Register', form=form)

        # Hash password for security
        hashed_password = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password=hashed_password,favorites=json.dumps([]))

        db.session.add(user)
        db.session.commit()

        session['username'] = user.username # Store username in session
        return redirect(url_for('main_page'))

    return render_template(
        'register.html',
        title='Register',
        form=form
    )


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # Check if user exists and password is correct
        if not user:
            flash("No account found with that email.", "email")
        elif not check_password_hash(user.password, form.password.data):
            flash("Incorrect password.", "password")
        else:
            session['username'] = user.username  # Store username in session
            return redirect(url_for("main_page"))
    return render_template(
        "login.html",
        title="Login",
        form=form
    )


@app.route("/main-page", methods=["GET", "POST"])
def main_page():
    # Main Page Set-Up
    username = session.get('username')
    if not username:
        session.clear()  
        return redirect(url_for('login'))  
    
    page = int(request.args.get('page', 1))
    page_size = 10
    news_data = []

    show_latest = False
    user_query = None

    # Saves user's last search 
    if request.method == "POST":
        user_query = request.form.get("query")
        session['last_query'] = user_query
    elif "page" in request.args and "last_query" in session:
        user_query = session['last_query']
    else:
        session.pop('last_query', None) # When reentering the page, delete last search

    # Latest 50 News from User's Search Section
    if user_query:
        subtitle = f"Results for '{user_query}'"
        show_latest = True

        # Filters 100 articles checking they have all the necessary info
        all_articles = newsapi.get_everything(
            q=user_query,
            language='en',
            sort_by="relevancy",
            page_size=100
        )

        valid_all_articles = [
            article for article in all_articles['articles']
            if article.get('title') and article.get('author') and article.get('url') and
            article.get('publishedAt') and article.get('content') and article.get('description') and
            article.get('urlToImage')
        ]

        # Take the first 50 articles
        valid_all_articles = valid_all_articles[:50]

        # Save the information of each article
        global saved_latest_articles
        saved_latest_articles = valid_all_articles


        # Calculate the start and end of news' info for display box
        start = (page - 1) * page_size
        end = start + page_size

        articles_to_show = valid_all_articles[start:end]

        news_data = [
            (
                article['title'].split('-')[0].strip(),
                article['publishedAt'][:10],
                article['author'],
                article['description'],
                article['urlToImage'],
                article['url']

            )
            for article in articles_to_show
        ]
    else:
        subtitle = None

    # Top News in the World Section
    top_all_articles = newsapi.get_top_headlines(language='en', page_size=30)

    valid_articles = [
        article for article in top_all_articles['articles']
        if article.get('title') and article.get('author') and article.get('publishedAt') and article.get('description')
    ]

    valid_articles = valid_articles[:7]
    # Save the information of each article
    global saved_top_articles
    saved_top_articles = valid_articles

    top_news_data = [
        (
            article['title'].split('-')[0].strip(),
            article['publishedAt'][:10],
            article['author'],
            article['description'],
            article['urlToImage'],
            article['url']

        )
        for article in valid_articles
    ]


    # In case there is no image available
    default_image = url_for('static', filename='images/news-default.webp')

    return render_template(
        "main-page.html",
        news_data=news_data,
        subtitle=subtitle,
        userName=username,
        top_news_data=top_news_data,
        default_image=default_image,
        current_page=page,
        show_latest=show_latest
    )

@app.route("/article/<int:index>")
def show_article(index):
    # Load the selected article
    if index >= len(saved_latest_articles):
        return "This article has not been found", 404

    article = saved_latest_articles[index]
    username = session.get('username')

    if not username:
        session.clear()  
        return redirect(url_for('login'))  

    # Get the summary for the given article (index).
    # If no summary has been saved yet ("Empty"), generate a new one using Gemini AI
    # and store it for future use or page refreshing
    url = article['url']
    if saved_latest_summaries[index] == "Empty":
        response = model.generate_content("Summarize this article (at least 100 words) " + url)
        summary = response.text
        saved_latest_summaries[index] = summary
    else:
        summary = saved_latest_summaries[index]

    return render_template(
        "article.html",
        article=article,
        userName=username,
        summary=summary,
        favorited=False
    )

@app.route("/top-article/<int:index>")
def show_top_article(index):
    # Load the selected article
    if index >= len(saved_top_articles):
        return "This article has not been found", 404

    article = saved_top_articles[index]
    username = session.get('username')

    if not username:
        session.clear()  
        return redirect(url_for('login'))  

    # Get the summary for the given article (index).
    # If no summary has been saved yet ("Empty"), generate a new one using Gemini AI
    # and store it for future use or page refreshing
    url = article['url']
    if saved_top_summaries[index] == "Empty":
        response = model.generate_content("Summarize this article (at least 200 words):" + url)
        summary = response.text
        saved_top_summaries[index] = summary
    else:
        summary = saved_top_summaries[index]

    return render_template(
        "article.html",
        article=article,
        userName=username
        ,summary=summary,
        favorited=False
    )


@app.route("/add-favorite", methods=["POST"])
def add_favorite():
    username = session.get('username')
    if not username:
        session.clear()  
        return redirect(url_for('login'))  

    # Get article's information
    new_favorite = {
        "title": request.form.get("title"),
        "publishedAt": request.form.get("publishedAt"),
        "author": request.form.get("author"),
        "summary": request.form.get("summary"),
        "description": request.form.get("description"),
        "urlToImage": request.form.get("urlToImage"),
        "url": request.form.get("url")
    }
    
    # Check if the article is already in the user's favorites
    user = User.query.filter_by(username=username).first()
    favorites = json.loads(user.favorites or "[]")
    if any(fav.get("url") == new_favorite["url"] for fav in favorites):
        return redirect(request.referrer) # Go back to the same page without changes

    # Go back to the same page adding the new favorite article
    # in the user's favorites
    favorites.append(new_favorite)
    user.favorites = json.dumps(favorites)
    db.session.commit()

    return redirect(request.referrer)

@app.route("/remove-favorite", methods=["POST"])
def remove_favorite():
    new_favorite = {
        "url": request.form.get("url")
    }

    username = session.get('username')
    if not username:
        session.clear()  
        return redirect(url_for('login'))  
    
    user = User.query.filter_by(username=username).first()
    favorites = json.loads(user.favorites or "[]")

    new_favs = [fav for fav in favorites if fav.get('url') != new_favorite['url']]
    user.favorites = json.dumps(new_favs)
    db.session.commit()

    return redirect(url_for("main_page"))

@app.route("/user-page", methods=["GET"])
def user_page():
    username = session.get('username')
    if not username:
        session.clear()
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=username).first()
    username_form = UpdateUsernameForm()
    email_form = UpdateEmailForm()
    password_form = ChangePasswordForm()

    favorites = json.loads(user.favorites or "[]")
    has_favorites = bool(favorites)

    if not has_favorites:
        return render_template(
            "user-page.html",
            userName=username,
            articles=[],
            has_favorites=False,
            current_page=1,
            total_pages=1,
            username_form=username_form,
            email_form=email_form,
            password_form=password_form
        )

    articles = favorites

    page = int(request.args.get('page', 1))
    page_size = 3
    total_pages = math.ceil(len(articles) / page_size)

    start = (page - 1) * page_size
    end = start + page_size
    articles_to_show = articles[start:end]

    return render_template(
        "user-page.html",
        userName=username,
        articles=articles_to_show,
        has_favorites=has_favorites,
        current_page=page,
        total_pages=total_pages,
        username_form=username_form,
        email_form=email_form,
        password_form=password_form
    )


@app.route("/update-username", methods=["POST"])
def update_username():
    username_form = UpdateUsernameForm()
    if username_form.validate_on_submit():
        user = User.query.filter_by(username=session.get('username')).first()
        if not user:
            session.clear()
            return redirect(url_for('login'))

        if not check_password_hash(user.password, username_form.current_password.data):
            flash("Incorrect password for username update.", "username_password")
        else:
            existing_user = User.query.filter_by(username=username_form.username.data).first()
            if existing_user and existing_user != user:
                flash("This username is already taken.", "username")
            else:
                user.username = username_form.username.data
                db.session.commit()
                session["username"] = user.username
                flash("Username updated successfully.", "username_success")
    else:
        for field, errors in username_form.errors.items():
            for error in errors:
                flash(error, "username")

    return redirect(url_for("user_page"))


@app.route("/update-email", methods=["POST"])
def update_email():
    email_form = UpdateEmailForm()
    if email_form.validate_on_submit():
        user = User.query.filter_by(username=session.get('username')).first()
        if not user:
            session.clear()
            return redirect(url_for('login'))

        if not check_password_hash(user.password, email_form.current_password.data):
            flash("Incorrect password for email update.", "email_password")
        else:
            existing_email = User.query.filter_by(email=email_form.email.data).first()
            if existing_email and existing_email != user:
                flash("This email is already taken.", "email")
            else:
                user.email = email_form.email.data
                db.session.commit()
                flash("Email updated successfully.", "email_success")
    else:
        for field, errors in email_form.errors.items():
            for error in errors:
                flash(error, "email")

    return redirect(url_for("user_page"))


@app.route("/change-password", methods=["POST"])
def change_password():
    password_form = ChangePasswordForm()
    if password_form.validate_on_submit():
        user = User.query.filter_by(username=session.get('username')).first()
        if not user:
            session.clear()
            return redirect(url_for('login'))

        if not check_password_hash(user.password, password_form.current_password.data):
            flash("Incorrect current password for password update.", "password_current")
        else:
            user.password = generate_password_hash(password_form.new_password.data)
            db.session.commit()
            flash("Password changed successfully.", "password_success")
    else:
        for field, errors in password_form.errors.items():
            for error in errors:
                flash(error, "password")

    return redirect(url_for("user_page"))


@app.route("/favorite-article/<int:index>")
def show_fav_article(index):
    username = session.get('username')
    user = User.query.filter_by(username=username).first()
    favorites = json.loads(user.favorites or "[]")
    article = favorites[index]

    return render_template(
        "article.html",
        article=article,
        userName=username,
        summary=article['summary'],
        favorited=True
    )


@app.route("/logout")
def logout():
    session.clear()  
    return redirect(url_for("login"))


@app.route("/update_server", methods=["POST"])
def webhook():
    # Auto update server in PythonAnywhere from the original GitHub repository
    if request.method == 'POST':
        repo = git.Repo('/home/week2proj/mysite/SEO_Project_Final')
        origin = repo.remotes.origin
        origin.pull()
        return "Updated PythonAnyWhere successfully", 200
    else:
        return "Wrong event type", 400


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
