import os
from dotenv import load_dotenv
import git

from flask import Flask, render_template, url_for, flash, redirect, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_behind_proxy import FlaskBehindProxy

from werkzeug.security import generate_password_hash, check_password_hash

from forms import RegistrationForm, LoginForm
from newsapi import NewsApiClient
from google import genai


def configure():
    load_dotenv()


configure()
saved_latest_articles = []


NEWS_API_KEY = os.getenv("NEWS_API_KEY")
if not NEWS_API_KEY:
    raise ValueError("Missing `NEWS_API_KEY` in .env file")

newsapi = NewsApiClient(api_key=NEWS_API_KEY)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Missing `GEMINI_API_KEY` in .env file")

client = genai.Client(api_key=GEMINI_API_KEY)

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
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)

        # Get user's username for later
        session['username'] = user.username

        db.session.add(user)
        db.session.commit()
        return redirect(url_for('main_page'))

    return render_template('register.html', title='Register', form=form)


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
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("main_page"))
    return render_template("login.html", title="Login", form=form)


@app.route("/main-page", methods=["GET", "POST"])
def main_page():
    # Main Page Set-Up
    username = session.get('username')

    page = int(request.args.get('page', 1))
    page_size = 10
    total_pages = 5
    news_data = []

    show_latest = False
    user_query = None

    if request.method == "POST":
        user_query = request.form.get("query")
        session['last_query'] = user_query
    elif "page" in request.args and "last_query" in session:
        user_query = session['last_query']
    else:
        session.pop('last_query', None)

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

    top_titles = [article['title'].split('-')[0].strip() for article in valid_articles]
    top_dates = [article['publishedAt'][:10] for article in valid_articles]
    top_authors = [article['author'] for article in valid_articles]
    top_descriptions = [article['description'] for article in valid_articles]
    top_thumbnails = [article['urlToImage'] for article in valid_articles]
    top_sources = [article['url'] for article in valid_articles]

    top_news_data = list(zip(top_titles, top_dates, top_authors, top_descriptions, top_thumbnails, top_sources))

    # In case there is no image available
    default_image = url_for('static', filename='images/news-default.webp')

    return render_template(
        "main-page.html",
        news_data=news_data,
        subtitle=subtitle,
        userName=username,
        top_news_data=top_news_data,
        default_image=default_image,
        top_dates=top_dates,
        current_page=page,
        total_pages=total_pages,
        show_latest=show_latest
    )


@app.route("/article/<int:index>")
def show_article(index):
    # Load the selected article
    if index >= len(saved_latest_articles):
        return "This article has not been found", 404

    article = saved_latest_articles[index]
    username = session.get('username')

    url = article['url']
    response = client.models.generate_content( model="gemini-2.0-flash", contents="Summarize this news article (at least 250 words): " + url)
    summary = response.text
    return render_template("article.html", article=article,userName=username,summary=summary)


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
