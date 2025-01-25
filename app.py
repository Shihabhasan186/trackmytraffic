from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
import mysql.connector
from datetime import timedelta
import os
from functools import wraps
import cv2
import numpy as np
from datetime import datetime
import time
import torch
import easyocr

app = Flask(__name__)
app.secret_key = os.urandom(24)  # This generates a new key each time the server starts
app.permanent_session_lifetime = timedelta(minutes=30)  # Session expires after 30 minutes

# Static credentials
VALID_CREDENTIALS = {
    'admin': 'admin',
    'user': 'password'
}

app.config['MAIL_SERVER']='live.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'api'
app.config['MAIL_PASSWORD'] = '41aad77a07395d0b11832f31100fb782'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# Initialize the Mail extension
mail = Mail(app)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'numberplates_speed'
}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Database connection helper
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in VALID_CREDENTIALS and VALID_CREDENTIALS[username] == password:
            session.permanent = True
            session['logged_in'] = True
            session['username'] = username
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    if session.get('logged_in'):
        session.clear()
        flash('You have been successfully logged out!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get total vehicles
            cursor.execute("SELECT COUNT(*) as total FROM my_data")
            total_vehicles = cursor.fetchone()['total']
            
            # Get vehicles exceeding speed limit (> 5.0 km/h)
            cursor.execute("SELECT COUNT(*) as total FROM my_data WHERE speed > 5.0")
            speed_violations = cursor.fetchone()['total']
            
            # Calculate total fines (same as speed violations for now)
            total_fines = speed_violations
            
            cursor.close()
            conn.close()
            
            return render_template('dashboard.html',
                                total_vehicles=total_vehicles,
                                speed_violations=speed_violations,
                                total_fines=total_fines)
        except Exception as e:
            flash(f'Error fetching dashboard data: {str(e)}', 'error')
            print(f"Dashboard Error: {e}")  # For debugging
            
    return render_template('dashboard.html',
                        total_vehicles=0,
                        speed_violations=0,
                        total_fines=0)

@app.route('/vehicle_list')
@login_required
def vehicle_list():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM my_data")
            vehicles = cursor.fetchall()
            cursor.close()
            connection.close()
            return render_template('vehicle_list.html', vehicles=vehicles)
        except Exception as e:
            flash(f'Error fetching vehicle data: {str(e)}', 'error')
            print(f"Database Error: {e}")
    return render_template('vehicle_list.html', vehicles=[])

@app.route('/fine')
@login_required
def fine():
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM my_data")
            all_vehicles = cursor.fetchall()
            
            fines = []
            for vehicle in all_vehicles:
                try:
                    speed_str = vehicle[5]
                    if isinstance(speed_str, str):
                        speed_value = float(speed_str.replace(" km/h", ""))
                    else:
                        speed_value = float(speed_str)
                        
                    if speed_value > 5.0:
                        fines.append(vehicle)
                except ValueError:
                    continue
                    
            cursor.close()
            connection.close()
            return render_template('fine.html', fines=fines)
        except Exception as e:
            flash(f'Error fetching fine data: {str(e)}', 'error')
            print(f"Database Error: {e}")
    
    return render_template('fine.html', fines=[])

@app.route('/about')
def about():
    return render_template('about.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.route("/send_email/<int:vehicle_id>", methods=["POST"])
def send_email_route(vehicle_id):
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM my_data WHERE id = %s", (vehicle_id,))
        vehicle = cursor.fetchone()

        if vehicle:
            vehicle_number = vehicle[5]  # Number plate
            speed = vehicle[6]  # Speed

            # Send the email using Flask-Mail
            send_email(vehicle_id, vehicle_number, speed)
            
            cursor.close()
            connection.close()
            return '', 200  # Return success status
        
        cursor.close()
        connection.close()
        return 'Vehicle not found', 404
        
    except Exception as e:
        print(f"Failed to send email: {e}")
        if connection:
            connection.close()
        return 'Failed to send email', 500

def send_email(vehicle_id, vehicle_number, speed):
    subject = "Alert! Fined For Over Speeding"
    body = f"Warning: Your vehicle ID: {vehicle_id}, Number: {speed} has exceeded the speed limit. Your vehicle speed was : {vehicle_number} km/h. You have been fined with 1000 BDT. Please submit the fines with in the due date otherwise you will be given penalty by the Road and Transport Ministry, Government of Bangladesh"

    try:
        msg = Message(
            subject=subject,
            body=body,
            sender='hello@demomailtrap.com',
            recipients=["sfsourov41@gmail.com"],
        )
        mail.send(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    app.run(debug=True)
