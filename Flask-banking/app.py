import os
from datetime import datetime
from forms import  CreateForm, LoginForm, WithdrawForm, top_up_id, TransferForm, DeleteForm
from flask import Flask, session, render_template, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
# from sqlalchemy import event
# from sqlalchemy import DDL

app = Flask(__name__)
# Key for Forms
app.config['SECRET_KEY'] = 'mysecretkey'
############################################

        # SQL DATABASE AND MODELS

##########################################
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector.com'
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
Migrate(app,db)

class Account(db.Model):

    __tablename__ = 'accounts'
    id = db.Column(db.Integer,primary_key = True)
    name = db.Column(db.String(80),unique=True)
    password = db.Column(db.Text) #To be HASHED
    balance = db.Column(db.Float)
    active = db.Column(db.Boolean,default=True)

    def top_up(self,type,amount):
        if type == 'withdraw':
            amount *= -1
        if self.balance + amount < 0:
            return False #Unsuccessful
        else:
            self.balance += amount
            return True #Successful

    def __init__(self,name, password, balance=0):
        self.name = name
        self.password = generate_password_hash(password) #HASHED
        self.balance = balance

    def __repr__(self):
        return f"Account name is {self.name} with account number {self.id}"

class Transaction(db.Model):

    __tablename__ = 'transactions'
    id = db.Column(db.Integer,primary_key = True)
    transaction_type = db.Column(db.Text)
    description = db.Column(db.Text)
    amount = db.Column(db.Float)
    date = db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    account_id = db.Column(db.Integer,db.ForeignKey('accounts.id'),nullable=False)
    account = db.relationship('Account',backref=db.backref('transactions', lazy=True))

    def __init__(self,transaction_type, description, account_id, amount=0):
        self.transaction_type = transaction_type
        self.description = description
        self.account_id = account_id
        self.amount = amount

    def __repr__(self):
        return f"Transaction {self.id}: {self.transaction_type} on {self.date}"

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = CreateForm()

    if form.validate_on_submit():
        name = form.name.data
        password = form.password.data #To be HASHED
        if form.balance.data > 0:
            balance = form.balance.data
        else:
            balance = 0

        # Add new bank account to database
        new_account = Account(name,password,balance)
        db.session.add(new_account)
        db.session.commit()
        new_transaction = Transaction('top up','account opening',new_account.id,balance)
        db.session.add(new_transaction)
        db.session.commit()
        session['username'] = new_account.name

        return redirect(url_for('my_account'))

    return render_template('register.html',form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        id = form.id.data
        password = form.password.data #To be HASHED
        account = Account.query.get(id)
        if check_password_hash(account.password,password):
            session['username'] = account.name
            return redirect(url_for('my_account'))
        else:
            return 'Phone number and pin doesn’t match'

    return render_template('login.html',form=form)


@app.route('/my_account', methods=['GET', 'POST'])
def my_account():
    withdraw_form = WithdrawForm()
    top_up = top_up_id()
    transfer_form = TransferForm()
    if session['username'] is None:
        return render_template('my_account.html')
    user = session['username']
    account = Account.query.filter_by(name=user).first()
    transactions = Transaction.query.filter_by(account_id=account.id).order_by(Transaction.date.desc())

    if top_up_id.deposit.data and top_up_id.validate():
        id = account.id
        amount = top_up_id.amount.data
        account = Account.query.get(id)
        if account.deposit_withdraw('top_up',amount):
            new_transaction = Transaction('top up','self deposit',account.id,amount)
            db.session.add(new_transaction)
            db.session.commit()
            return redirect(url_for('my_account'))
        else:
            #flash = you do not have sufficient funds to perform this operation
            return redirect(url_for('my_account'))
    elif withdraw_form.withdraw.data and withdraw_form.validate():
        id = account.id
        amount = withdraw_form.amount.data
        account = Account.query.get(id)
        if account.deposit_withdraw('withdraw',amount):
            new_transaction = Transaction('withdraw','self withdraw',account.id,(amount*(-1)))
            db.session.add(new_transaction)
            db.session.commit()
            return redirect(url_for('my_account'))
        else:
            #flash = you do not have sufficient funds to perform this operation
            return redirect(url_for('my_account'))
    elif transfer_form.transfer.data and transfer_form.validate():
        id = account.id
        amount = transfer_form.amount.data
        account_id = transfer_form.account_id.data
        password = transfer_form.password.data #To be HASHED
        account = Account.query.get(id)
        if check_password_hash(account.password,password):
            if account.deposit_withdraw('withdraw',amount):
                new_transaction = Transaction('transfer out',f'transfer to account {account_id}',account.id,(amount*(-1)))
                db.session.add(new_transaction)
                recipient = Account.query.get(account_id)
                if recipient.deposit_withdraw('deposit',amount):
                    new_transaction2 = Transaction('transfer in',f'transfer from account {account.id}',account_id,amount)
                    db.session.add(new_transaction2)
                    db.session.commit()
                    return redirect(url_for('my_account'))
                else:
                    #flash = you do not have sufficient funds to perform this operation
                    return redirect(url_for('my_account'))
            else:
                #flash = you do not have sufficient funds to perform this operation
                return redirect(url_for('my_account'))
        else:
            return '<h1>Invalid Account Password</h1>'

    return render_template('my_account.html',user=user,account=account,transactions=transactions,withdraw_form=withdraw_form,deposit_form=top_up,transfer_form=transfer_form)

if __name__ == '__main__':
    app.run(debug=False)
