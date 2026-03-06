from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import boto3
from decimal import Decimal
import uuid
import os
from boto3.dynamodb.conditions import Attr

app = Flask(_name_)

# ==============================
# CONFIG
# ==============================
app.secret_key = os.environ.get("SECRET_KEY", "moviemagic_super_secret")

AWS_REGION = "us-east-1"
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "YOUR_SNS_TOPIC_ARN")  # Set this on EC2

# ==============================
# AWS SERVICES
# ==============================
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
sns = boto3.client("sns", region_name=AWS_REGION)

users_table    = dynamodb.Table("MovieMagic_Users")
bookings_table = dynamodb.Table("MovieMagic_Bookings")

# ==============================
# HELPERS
# ==============================
def replace_decimals(obj):
    if isinstance(obj, list):
        return [replace_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: replace_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

def send_email(username, name, movie, seat, tickets, ticket_id):
    """Send SNS booking confirmation email"""
    try:
        message = f"""
Hello {name},

Your Movie Magic booking is CONFIRMED! 🎬

----------------------------------
Ticket ID  : {ticket_id}
Movie      : {movie}
Seat       : {seat}
Tickets    : {tickets}
Booked By  : {username}
Date/Time  : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
----------------------------------

Enjoy your movie! 🍿
- Team Movie Magic
        """
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="🎟 MovieMagic Ticket Confirmation",
            Message=message
        )
        print("✅ SNS email sent")
    except Exception as e:
        print("SNS ERROR:", e)  # Don't crash app if SNS fails

# ==============================
# HOME
# ==============================
@app.route("/")
def home():
    return redirect("/login")

# ==============================
# REGISTER
# ==============================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            username = request.form["username"]
            password_raw = request.form["password"]

            # Check if user exists
            response = users_table.get_item(Key={"username": username})
            if "Item" in response:
                flash("Username already taken. Try another.")
                return redirect("/register")

            # Save to DynamoDB with hashed password
            users_table.put_item(Item={
                "username": username,
                "password": generate_password_hash(password_raw),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            flash("Registered successfully! Please login.")
            return redirect("/login")

        except Exception as e:
            print("Register Error:", e)
            flash("Registration failed. Try again.")

    return render_template("register.html")

# ==============================
# LOGIN
# ==============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        try:
            response = users_table.get_item(Key={"username": username})
            if "Item" in response:
                user = response["Item"]
                if check_password_hash(user["password"], password):
                    session["user"] = username
                    return redirect("/booking")

            flash("Invalid username or password.")
        except Exception as e:
            print("Login Error:", e)
            flash("Login failed. Try again.")

    return render_template("login.html")

# ==============================
# LOGOUT
# ==============================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

# ==============================
# BOOKING PAGE
# ==============================
@app.route("/booking")
def booking():
    if "user" not in session:
        return redirect("/login")
    return render_template("index.html", user=session["user"])

# ==============================
# BOOK TICKET
# ==============================
@app.route("/book", methods=["POST"])
def book():
    if "user" not in session:
        return redirect("/login")

    try:
        name    = request.form["name"]
        movie   = request.form["movie"]
        seat    = request.form["seat"]
        tickets = request.form["tickets"]

        ticket_id = f"MM-{str(uuid.uuid4())[:8].upper()}"

        # Check if seat already booked
        response = bookings_table.scan(
            FilterExpression=Attr("movie").eq(movie) & Attr("seat").eq(seat)
        )
        if response["Items"]:
            flash("❌ Seat already booked! Please choose another.")
            return redirect("/booking")

        # Save booking to DynamoDB
        bookings_table.put_item(Item={
            "ticket_id": ticket_id,
            "username":  session["user"],
            "name":      name,
            "movie":     movie,
            "seat":      seat,
            "tickets":   tickets,
            "time":      datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        # Send SNS email notification
        send_email(session["user"], name, movie, seat, tickets, ticket_id)

        return render_template("success.html")

    except Exception as e:
        print("Booking Error:", e)
        flash("Booking failed. Try again.")
        return redirect("/booking")

# ==============================
# MY BOOKINGS
# ==============================
@app.route("/bookings")
def bookings():
    if "user" not in session:
        return redirect("/login")

    try:
        response = bookings_table.scan(
            FilterExpression=Attr("username").eq(session["user"])
        )
        user_bookings = replace_decimals(response.get("Items", []))
    except Exception as e:
        print("Bookings Error:", e)
        user_bookings = []

    return render_template("bookings.html", bookings=user_bookings)

# ==============================
# RUN
# ==============================
if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000, debug=True)
