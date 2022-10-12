import os

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
    rows = db.execute("SELECT * FROM stocks  WHERE buyer_id = ? ORDER BY time DESC", session["user_id"])

    if len(rows) != 0:
        user = db.execute("select * from users where id = ?", session["user_id"])
        current_cash = round(user[0]["cash"], 2)
        final_cash = rows[0]["final_cash"]
        return render_template("index.html", rows=rows, final_cash=final_cash)
    current_cash = round(10000, 2)
    return render_template("index.html", current_cash=current_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        if not request.form.get("shares").isdigit():
            return apology("Invalis shares", 400)
        shares = int(request.form.get("shares"))
        quotes = lookup(symbol)
        if not symbol or quotes == None:
            return apology("Invalid symbol", 400)

        elif not request.form.get("shares"):
            return apology("must provide shares", 400)
        elif shares < 0:
            return apology("Shares must be a positive integer", 400)
        else:
            price = round(quotes["price"], 2)
            name = quotes["name"]
            person = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
            cash = round(person[0]["cash"], 2)
            total = round((price * shares), 2)
            final_cash = round(cash - total, 2)

            if final_cash < 0:
                return apology("Not enough money", 403)
            db.execute("UPDATE users SET cash = ? WHERE id = ?", final_cash, session["user_id"])
            now = datetime.now()
            dt = now.strftime("%d/%m/%Y %H:%M:%S")
            db.execute("INSERT INTO purchase (buyer_id, symbol, name, shares, price, total, final_cash,time) VALUES (?,?,?,?,?,?,?,?)",
                       session["user_id"], symbol, name, shares, price, total, final_cash, dt)
            stocks = db.execute(
                "select buyer_id,symbol,name,sum(shares),price,sum(total),min(final_cash),min(time) from purchase  where buyer_id = ? and name = ? group by name", session["user_id"], name)
            shares = stocks[0]["sum(shares)"]
            price = stocks[0]["price"]
            total = stocks[0]["sum(total)"]
            final_cash = stocks[0]["min(final_cash)"]
            db.execute("DELETE FROM stocks WHERE name = ?", name)
            db.execute("INSERT INTO stocks (buyer_id, symbol, name, shares, price, total, final_cash,time) VALUES (?,?,?,?,?,?,?,?)",
                       session["user_id"], symbol, name, shares, price, total, final_cash, dt)
            # rows = db.execute("SELECT * FROM stocks WHERE buyer_id = ? ORDER BY time DESC", session["user_id"])
            # if len(rows) != 0:
            #     final_cash = rows[0]["final_cash"]
            #     return render_template("index.html", rows = rows, final_cash = final_cash)
            # return render_template("index.html")
            return redirect("/buy")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM purchase WHERE buyer_id = ? ORDER BY time DESC", session["user_id"])
    if len(rows) != 0:
        return render_template("history.html", rows=rows)
    return render_template("history.html")


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
        symbol = request.form.get("symbol")
        quotes = lookup(symbol.upper())
        if quotes == None:
            return apology("Invalid symbol", 400)
        else:
            name = quotes["name"]
            price = quotes["price"]
            symbol = quotes["symbol"]
            return render_template("quoted.html", name=name, price=price, symbol=symbol)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if not username:
            return apology("must provide username", 400)
        elif len(rows) != 0:
            return apology("invalid username", 400)
        elif not password:
            return apology("must provide password", 400)
        elif not confirmation or confirmation != password:
            return apology("invalid password", 400)
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = rows[0]["id"]
            return redirect("/login")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        rows = db.execute("SELECT * FROM stocks WHERE buyer_id = ? ORDER BY time DESC", session["user_id"])
        final_cash = rows[0]["final_cash"]
        list_symbols = []
        for row in rows:
            list_symbols.append(row["symbol"])
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        for row in rows:
            if row["symbol"] == symbol:

                owned_name = row["name"]
                owned_shares = row["shares"]
                owned_price = row["price"]

        if not symbol:
            return apology("must provide symbole", 403)
        elif symbol not in list_symbols:
            return apology("You Don't own any shares of that stock", 403)
        elif shares < 0:
            return apology("shares must be a positive integer", 403)
        elif shares > owned_shares:
            return apology("Not enough shares", 403)

        else:
            now = datetime.now()
            dt = now.strftime("%d/%m/%Y %H:%M:%S")
            total = round((owned_price * (shares)), 2)
            final_cash += total
            db.execute("INSERT INTO purchase (buyer_id, symbol, name, shares, price, total, final_cash,time) VALUES (?,?,?,?,?,?,?,?)",
                       session["user_id"], symbol, owned_name, -shares, owned_price, -total, final_cash, dt)
            stocks = db.execute(
                "select buyer_id,symbol,name,sum(shares),price,sum(total),min(final_cash),min(time) from purchase  where buyer_id = ? and name = ? group by name", session["user_id"], owned_name)
            shares = stocks[0]["sum(shares)"]
            price = stocks[0]["price"]
            total = stocks[0]["sum(total)"]
            db.execute("DELETE FROM stocks WHERE name = ?", owned_name)
            db.execute("INSERT INTO stocks (buyer_id, symbol, name, shares, price, total, final_cash,time) VALUES (?,?,?,?,?,?,?,?) ",
                       session["user_id"], symbol, owned_name, shares, price, total, final_cash, dt)
            db.execute("DELETE FROM stocks WHERE shares = 0")
            # rows = db.execute("SELECT * FROM stocks WHERE buyer_id = ? ORDER BY time DESC", session["user_id"])
            # if len(rows) != 0:
            #     final_cash = rows[0]["final_cash"]
            #     return render_template("index.html", rows = rows, final_cash = final_cash)
            # else:
            #     return render_template("index.html")
            return redirect("/sell")

    else:
        rows = db.execute("SELECT * FROM stocks WHERE buyer_id = ? ORDER BY time DESC", session["user_id"])
        if len(rows) != 0:
            list_symbols = []
            for row in rows:
                list_symbols.append(row["symbol"])
            return render_template("sell.html", list_symbols=list_symbols)
        return render_template("sell.html")


@app.route("/deposite", methods=["GET", "POST"])
@login_required
def deposite():
    if request.method == "POST":
        price = int(request.form.get("price"))
        user = db.execute("select * from users where id = ?", session["user_id"])
        current_cash = user[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", current_cash + price, session["user_id"])
        return redirect("/")
    else:
        return render_template("deposite.html")

