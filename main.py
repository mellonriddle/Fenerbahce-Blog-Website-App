from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from datetime import date
from flask_ckeditor import CKEditor
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os
from dotenv import load_dotenv

# Getting environment variables
load_dotenv(".env")

# Starting the Flask APP
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("secret_key")

ckeditor = CKEditor(app)
Bootstrap(app)

login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app, size=100, rating='g', default='retro',
                    force_default=False, force_lower=False, use_ssl=False, base_url=None)


# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_blog")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="writer")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    commenter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    writer = relationship("User", back_populates="comments")
    blog_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_blog = relationship("BlogPost", back_populates="comments")


db.create_all()


# Getting user information from database for login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Some function works for only admin
def admin_only(func):
    @wraps(func)
    def wrapper_function(*args, **kwargs):
        try:
            if current_user.id == 1:
                return func(*args, **kwargs)
            else:
                return abort(403)
        except AttributeError:
            return "<h1> need to log in first </h1>"
    return wrapper_function


# This is our homepage
@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    users = User.query.all()
    return render_template("index.html", all_posts=posts, users=users, logged_in=current_user.is_authenticated)


# This is register page, grabs data from user and save it to DB
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("That email already exist in db!")
            return redirect(url_for('login'))
        else:
            hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
            new_user = User(name=form.name.data, email=form.email.data, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


# Page for users to login, checks database with user inputs
@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            user_password = user.password
            if check_password_hash(user_password, form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash("Wrong Password!")
                return redirect(url_for('login'))
        else:
            flash("Wrong Entry!")
            return redirect(url_for('login'))
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


# Log out function
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


# Blog Posts web pages, getting data from database
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    users = User.query.all()
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_anonymous:
            new_comment = Comment(text=comment_form.comment.data, blog_id=post_id, commenter_id=current_user.id)
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("Need to log in to comment!")
            return redirect(url_for('login'))

    comments = Comment.query.all()
    blog_comments = [ct for ct in comments if ct.blog_id == post_id]
    return render_template("post.html", post=requested_post, users=users, comment_form=comment_form,
                           logged_in=current_user.is_authenticated, comments=blog_comments)


# About page for club
@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


# Contact and Support Page for club
@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


# Create Post page for authorized users
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


# Edit Post page for authorized users
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated)


# Delete Post function for authorized users
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# RUN
if __name__ == "__main__":
    app.run(debug=True)
