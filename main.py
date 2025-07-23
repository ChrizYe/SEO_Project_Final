from flask import Flask, render_template, url_for, flash, redirect, request, session
from forms import RegistrationForm, LoginForm
import git
from flask_behind_proxy import FlaskBehindProxy
from flask_sqlalchemy import SQLAlchemy


#Password hashing
from werkzeug.security import generate_password_hash, check_password_hash


# API SECTION
from newsapi import NewsApiClient
from dotenv import load_dotenv
import os

def configure():
    load_dotenv()

# Init
newsapi = NewsApiClient(api_key=os.getenv('my_key'))
# ! TO GET DATA BASE RUN:

# ! .\venv\Scripts\Activate.ps1
# ! $env:FLASK_APP = "main.py"
# ! python -m flask shell
# ! from (FILE NAME) import User
# ! User.query.all()



app = Flask(__name__)
proxied = FlaskBehindProxy(app)  # Enables proxy support
app.config['SECRET_KEY'] = 'd002cde69ced4dfd3544654676af1df8'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

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

        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            form.email.errors.append("This email is already registered.")
            return render_template('register.html', title='Register',form=form)

        existing_username = User.query.filter_by(username=form.username.data).first()
        if existing_username:
            form.username.errors.append("That username is already taken.")
            return render_template('register.html', title='Register', form=form)
        
        #! This is the password hashed
        hashed_password = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)

        session['username']= user.username # ! This is to get the user

        db.session.add(user)
        db.session.commit()
        return redirect(url_for('main_page'))  
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash("No account found with that email.", "email")
        elif not check_password_hash(user.password, form.password.data):
            flash("Incorrect password.", "password")
        else:
            session['username']= user.username # ! This is to get the user
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("main_page"))
    return render_template("login.html", title="Login", form=form)



@app.route("/main-page", methods=["GET", "POST"])
def main_page():

    configure()

    username = session.get('username')
    titles = authors = sources = dates = descriptions = thumbnails= information = []

    page = int(request.args.get('page',1))
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


    if user_query:

        show_latest = True

        all_articles = newsapi.get_everything(q=user_query, language='en',sort_by="relevancy",page_size=100)

        valid_all_articles=[article for article in all_articles['articles'] if article.get('title') and article.get('author') and article.get('url') and article.get('publishedAt') and article.get('content') and article.get('description') and article.get('urlToImage')]
        
        valid_all_articles = valid_all_articles[:50]

        titles = [article['title'].split('-')[0].strip() for article in valid_all_articles]
        dates = [article['publishedAt'][:10] for article in valid_all_articles]
        authors = [article['author'] for article in valid_all_articles]
        descriptions = [article['description'] for article in valid_all_articles]
        thumbnails = [article['urlToImage'] for article in valid_all_articles]
        sources = [article['url'] for article in valid_all_articles]
        information = [article['content'] for article in valid_all_articles]


        start = (page - 1) * page_size
        end = start + page_size

        titles = titles[start:end]
        dates = dates[start:end]
        authors = authors[start:end]
        descriptions = descriptions[start:end]
        thumbnails = thumbnails[start:end]
        sources = sources[start:end]
        information = information[start:end]

        news_data = zip(titles,dates,authors,descriptions,thumbnails,sources,information)

        subtitle = f"Results for '{user_query}'"
    else:
        subtitle = None


    # ! THIS IS FOR THE BENTO GRID NEWS
    top_titles = []
    top_authors = []
    top_descriptions = []
    top_thumbnails = []

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
    
    default_image = url_for('static', filename='images/news-default.webp')

    return render_template("main-page.html", news_data=news_data, subtitle=subtitle,userName=username,top_titles=top_titles, top_authors=top_authors,top_descriptions=top_descriptions,top_thumbnails=top_thumbnails,default_image=default_image,top_dates=top_dates, current_page=page,total_pages=total_pages, show_latest=show_latest)

@app.route("/update_server", methods=["POST"])

def webhook():
    if request.method == 'POST':
        repo = git.Repo('/home/week2proj/mysite/SEO_Project_Final')
        origin = repo.remotes.oringin
        origin.pull()
        return "Updated PythonAnyWhere successfully", 200
    else:
        return "Wrong event type", 400
    
if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")

    