import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///birthdays.db")

ids = db.execute("SELECT * FROM birthdays")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        # TODO: Add the user's entry into the database
        newName = request.form.get("name")
        newMonth = request.form.get("month")
        newDay = request.form.get("day")
        db.execute("INSERT INTO birthdays (name, month, day) VALUES (?, ?, ?)", newName, newMonth, newDay)

        return redirect("/")

    else:

        # TODO: Display the entries in the database on index.html

        return render_template("index.html", ids=ids)

@app.route("/removeBirthday", methods=["POST"])
def remove():
    removeBirthdayID = request.form.get("removeBirthday")
    db.execute("DELETE FROM birthdays WHERE id = ?", removeBirthdayID)

    return redirect("/")
