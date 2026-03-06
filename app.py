from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = "movie_secret"

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["movie_magic"]

bookings_collection = db["bookings"]
users_collection = db["users"]


# Home
@app.route("/")
def home():
    return redirect("/login")


# Register
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = {
            "username": username,
            "password": password
        }

        users_collection.insert_one(user)

        return redirect("/login")

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({
            "username": username,
            "password": password
        })

        if user:
            session["user"] = username
            return redirect("/booking")

        else:
            return "❌ Invalid login"

    return render_template("login.html")


# Logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


# Booking page
@app.route("/booking")
def booking():

    if "user" not in session:
        return redirect("/login")

    return render_template("index.html", user=session["user"])


# Book ticket
@app.route("/book", methods=["POST"])
def book():

    if "user" not in session:
        return redirect("/login")

    name = request.form["name"]
    movie = request.form["movie"]
    seat = request.form["seat"]
    tickets = request.form["tickets"]

    ticket_id = random.randint(1000, 9999)

    existing = bookings_collection.find_one({
        "movie": movie,
        "seat": seat
    })

    if existing:
        return "❌ Seat already booked"

    data = {
        "ticket_id": ticket_id,
        "username": session["user"],
        "name": name,
        "movie": movie,
        "seat": seat,
        "tickets": tickets,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    bookings_collection.insert_one(data)

    return render_template("success.html")


# Show user bookings
@app.route("/bookings")
def bookings():

    if "user" not in session:
        return redirect("/login")

    user_bookings = bookings_collection.find({
        "username": session["user"]
    })

    return render_template("bookings.html", bookings=user_bookings)


if __name__ == "__main__":
    app.run(debug=True)