import os

import re
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime


from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

purchaseTime = datetime.now()


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # ID of logged user
    loggedUser = session["user_id"]

    # User info
    userInfo = db.execute("SELECT username, cash FROM users WHERE id=?", loggedUser)

    # User stock summary
    userPurchases = db.execute("SELECT stock_name, stock_symbol, price, sum(amount), sum(total) FROM purchases WHERE user_id=? GROUP BY stock_name", loggedUser)
    for purchase in userPurchases:
        print(purchase)

    # New user display
    if not userPurchases:
        userBalance = userInfo[0]["cash"]

    # Existing user display
    else:
        userStock = userPurchases[0]["sum(total)"]
        userBalance = userInfo[0]["cash"] + userStock

    return render_template("index.html", userInfo=userInfo, userPurchases=userPurchases, userBalance=userBalance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        loggedUser = session["user_id"]
        # Check symbol
        stockSymbol = request.form.get("symbol").upper()
        if not stockSymbol or not lookup(stockSymbol):
            return apology("Incorrect selection!")

        # Cast input to integer and check its value
        try:
            stockAmount = int(request.form.get("shares"))
            if stockAmount <= 0:
                return apology("Input amount greater than 0.")

        # Check for client side tempering
        except ValueError:
            return apology(":(")

        # Check price
        selectedStock = lookup(stockSymbol)

        # Stock full name
        stockName = selectedStock["name"]

        # Incase no name
        if not stockName:
            stockName = stockSymbol

        # Check total
        stockPrice = selectedStock["price"]
        totalPrice = stockPrice * stockAmount
        transactionType = "BUY"

        # Check balance
        userBalance = db.execute("SELECT cash FROM users WHERE ID = ?", loggedUser)

        # Check if user has enough balance
        if userBalance[0]["cash"] < totalPrice:
            return apology("Balance too low.")

        # Execute purchase
        db.execute("INSERT INTO purchases (user_id, stock_name, stock_symbol, amount, price, total, transaction_type, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", loggedUser, stockName, stockSymbol, +(stockAmount), stockPrice, totalPrice, transactionType, purchaseTime)

        # Calculate new balance
        newBalance = userBalance[0]["cash"] - totalPrice

        # Update balance
        db.execute("UPDATE users SET cash=? WHERE id=?", newBalance, loggedUser)

        #Confirm payment
        flash("Purchase complete.")
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    eventHistory = db.execute("SELECT * FROM purchases WHERE user_id=?", session["user_id"])

    return render_template("history.html", eventHistory=eventHistory)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":

        # Get tag
        tag = request.form.get("symbol")

        # Check if tag exists
        info = lookup(tag)
        if not info:
            return apology("No such symbol.")

        return render_template("quotes.html", info=info)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Check for username
        newUser = request.form.get("username")
        if not newUser or len(newUser) < 4:
            return apology("Username > 4 characters!")

        # Check if username already exists
        userDB = db.execute("SELECT username FROM users")
        for user in userDB:
            if newUser in user['username']:
                return apology("Username already exists!")

        newPw = request.form.get("password")
        confirmPw = request.form.get("confirmation")

        # Check if there is a password and password length
        if not newPw or len(newPw) < 4:
            return apology("Password > 4 characters!")

        # Check if password and confirmation are identical
        if newPw != confirmPw:
            return apology("Password did not match!")

        # Hash password
        newPwHashed = generate_password_hash(newPw, method='pbkdf2:sha256', salt_length = 8)

        # Insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", newUser, newPwHashed)

        # Let user know he has successfully registered
        flash("Successfully registered. You can now log in.")

        return render_template("login.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    loggedUser = session["user_id"]
    userBalance = db.execute("SELECT cash FROM users WHERE id=?", loggedUser)
    userPurchases = db.execute("SELECT stock_name, stock_symbol, sum(amount) FROM purchases WHERE user_id=? GROUP BY stock_name", loggedUser)

    if request.method == "POST":

        # Check user input of shares, return apology in case of errors.
        try:
            sellAmount = int(request.form.get("shares"))
        except ValueError:
                return apology("Invalid amount.")

        # Get user input for symbol, return apology in case of errors.
        stockSymbol = request.form.get("symbol")
        selectedStock = lookup(stockSymbol)
        if not selectedStock:
            return apology("No such symbol.")

        # Check user stock for selected share.
        stockAmount = db.execute("SELECT sum(amount) FROM purchases WHERE stock_symbol=? AND user_id=?", stockSymbol, loggedUser)

        # Incase of some weird output return error. TODO: Send error log.
        if len(stockAmount) != 1:
            return apology("Oops something went wrong. Please contact support.")

        # Check input for negative integers and for exceeding users current supply of shares.
        if sellAmount <= 0 or sellAmount > stockAmount[0]['sum(amount)']:
            return apology("Invalid amount.")

        # Get full name
        stockName = selectedStock["name"]
        # Get total price (Price*Amount)
        stockPrice = selectedStock["price"]
        totalPrice = stockPrice * sellAmount
        # Type
        transactionType = "SELL"

        #Turn sell amount into negative before submiting query
        sellAmount = -(sellAmount)

        # Execute
        db.execute("INSERT INTO purchases (user_id, stock_name, stock_symbol, amount, price, total, transaction_type, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", loggedUser, stockName, stockSymbol, sellAmount, stockPrice, -(totalPrice), transactionType, purchaseTime)

        # Update user balance
        newUserBalance = userBalance[0]["cash"] + totalPrice
        db.execute("UPDATE users SET cash=? WHERE id=?", newUserBalance, loggedUser)

        # Let user know action was complete.
        flash("Shares sold.")
        return redirect("/")

    else:
        return render_template("sell.html", userPurchases=userPurchases)


@app.route("/balance", methods=["GET", "POST"])
@login_required
def balance():
    loggedUser = session["user_id"]
    currentBalance = db.execute("SELECT cash FROM users WHERE id=?", loggedUser)

    try:
        increaseBalance = int(request.form.get("balance"))
    except ValueError:
        return apology("Not an integer.")

    if increaseBalance < 0 or increaseBalance > 1000000:
        return apology("Enter a reasonable amount.")

    newBalance = currentBalance[0]['cash'] + increaseBalance
    db.execute("UPDATE users SET cash=? WHERE id=?", newBalance, loggedUser)

    return redirect("/")


