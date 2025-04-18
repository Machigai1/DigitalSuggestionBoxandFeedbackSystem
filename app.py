from flask import Flask, request, jsonify, send_from_directory
from flask_mysqldb import MySQL
from flask_cors import CORS
from datetime import datetime
from datetime import timedelta

import MySQLdb.cursors
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'youtube.com211'
app.config['MYSQL_DB'] = 'sfeedback_systemvC'

mysql = MySQL(app)

def delete_old_archived_suggestions():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Get the current date minus 3 months
        three_months_ago = datetime.now() - timedelta(days=90)
        three_months_ago_str = three_months_ago.strftime('%Y-%m-%d')

        # Delete suggestions older than 3 months with 'Resolved' status
        cursor.execute('''
            DELETE FROM SUGGESTION WHERE Status = 'Resolved' AND Date_submitted < %s
        ''', (three_months_ago_str,))
        
        cursor.execute('''
            DELETE FROM FEEDBACK WHERE Suggestion_id NOT IN (SELECT Suggestion_id FROM SUGGESTION)
        ''')
        
        mysql.connection.commit()
        cursor.close()

        print("Old archived suggestions deleted successfully.")
    
    except Exception as e:
        print(f"Error deleting old archived suggestions: {str(e)}")

# Serve Index Page (Login Page)
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Serve Static Files (HTML Pages)
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Student Registration Route
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    student_id = data['student_id']
    email = data['email']
    password = data['password']
    course = data['course']
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute('INSERT INTO STUDENTS (Student_ID, Email, Password, Course) VALUES (%s, %s, %s, %s)', 
                       (student_id, email, password, course))
        mysql.connection.commit()
        message = "Registration successful!"
    except MySQLdb.Error as e:
        message = f"An error occurred: {e}"
    finally:
        cursor.close()

    return jsonify({"message": message})

# Student Login Route
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data['email']
        password = data['password']
        
        if email == "admin" and password == "admin":
            # Admin Login
            return jsonify({"message": "Admin login successful!", "is_admin": True}), 200
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM STUDENTS WHERE Email = %s AND Password = %s', (email, password))
        account = cursor.fetchone()
        cursor.close()

        if account:
            return jsonify({"message": "Login successful!", "student_id": account['Student_ID'], "is_admin": False}), 200
        else:
            return jsonify({"message": "Invalid email or password."}), 401
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Suggestion Submission Route
@app.route('/submit_suggestion', methods=['POST'])
def submit_suggestion():
    try:
        data = request.json
        student_id = data['student_id']
        category_id = data['category_id']
        message = data['message']
        subcategory = data['subcategory']
        date_submitted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor = mysql.connection.cursor()
        cursor.execute('''INSERT INTO SUGGESTION (Student_id, Category_id, Subcategory, Message, Status, Date_submitted)
                          VALUES (%s, %s, %s, %s, 'No Action Yet', %s)''', 
                          (student_id, category_id, subcategory, message, date_submitted))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({"message": "Suggestion submitted successfully!"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Admin: Update Status to "Being Addressed"
@app.route('/update_status', methods=['POST'])
def update_status():
    try:
        data = request.json
        suggestion_id = data.get('suggestion_id')
        status = data.get('status')

        if not (suggestion_id and status):
            return jsonify({"message": "Missing suggestion ID or status"}), 400

        cursor = mysql.connection.cursor()
        cursor.execute('''UPDATE SUGGESTION SET Status = %s WHERE Suggestion_id = %s''', (status, suggestion_id))
        mysql.connection.commit()
        cursor.close()

        return jsonify({"message": f"Status updated to '{status}'"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Admin: Get All Pending Suggestions
@app.route('/get_pending_suggestions', methods=['GET'])
def get_pending_suggestions():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM SUGGESTION WHERE Status = 'No Action Yet'")
        suggestions = cursor.fetchall()
        cursor.close()
        
        return jsonify(suggestions), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Admin: Get Dashboard Data
@app.route('/get_dashboard_data', methods=['GET'])
def get_dashboard_data():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Get counts for Pending, Approved, and Denied suggestions
        cursor.execute("SELECT Status, COUNT(*) AS count FROM SUGGESTION GROUP BY Status")
        status_counts = {row["Status"]: row["count"] for row in cursor.fetchall()}

        # Get recent suggestions (latest 5)
        cursor.execute("SELECT Suggestion_id, Message, Status FROM SUGGESTION ORDER BY Date_submitted DESC LIMIT 5")
        recent_suggestions = cursor.fetchall()

        cursor.close()

        return jsonify({
            "noActionYet": status_counts.get("No Action Yet", 0),
            "actionTaken": status_counts.get("Action Taken", 0),
            "recentSuggestions": recent_suggestions
        }), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/get_being_addressed_suggestions')
def get_being_addressed_suggestions():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM SUGGESTION WHERE Status = 'Being Addressed' ORDER BY Date_submitted DESC")
        data = cursor.fetchall()
        cursor.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/update_response', methods=['POST'])
def update_response():
    data = request.json
    suggestion_id = data.get('suggestion_id')
    response_text = data.get('response')

    # Debugging logs to check incoming data
    print(f"Received data: suggestion_id={suggestion_id}, response={response_text}")

    # Ensure that suggestion_id and response_text are provided
    if not suggestion_id or not response_text:
        return jsonify({"message": "Suggestion ID and Response are required."}), 400

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Check if the suggestion_id exists in the SUGGESTION table
        cursor.execute('SELECT * FROM SUGGESTION WHERE Suggestion_id = %s', (suggestion_id,))
        suggestion = cursor.fetchone()

        # Debugging log to check if suggestion exists
        print(f"Suggestion found: {suggestion}")

        if not suggestion:
            return jsonify({"message": "Suggestion ID not found."}), 404

        # Update the response in the FEEDBACK table based on the suggestion_id
        cursor.execute('''UPDATE FEEDBACK 
                          SET Response = %s, Status = 'Being Addressed', Date_evaluated = NOW() 
                          WHERE Suggestion_id = %s''', (response_text, suggestion_id))

        # Check if the feedback was updated
        if cursor.rowcount == 0:
            return jsonify({"message": "No feedback found for the given suggestion ID."}), 404

        # Update the suggestion's status to "Being Addressed"
        cursor.execute('''UPDATE SUGGESTION SET Status = 'Being Addressed' WHERE Suggestion_id = %s''', (suggestion_id,))

        mysql.connection.commit()
        cursor.close()

        return jsonify({"message": "Response updated successfully and status set to 'Being Addressed'."}), 200

    except Exception as e:
        return jsonify({"message": "Failed to update response", "error": str(e)}), 500

@app.route('/mark_resolved', methods=['POST'])
def mark_resolved():
    data = request.json
    suggestion_id = data.get('suggestion_id')

    if not suggestion_id:
        return jsonify({"message": "Suggestion ID is required"}), 400

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Set Status as 'Resolved' in both SUGGESTION and FEEDBACK tables
        cursor.execute("UPDATE SUGGESTION SET Status = 'Resolved' WHERE Suggestion_id = %s", (suggestion_id,))
        cursor.execute("UPDATE FEEDBACK SET Status = 'Resolved' WHERE Suggestion_id = %s", (suggestion_id,))

        mysql.connection.commit()
        cursor.close()

        return jsonify({"message": "Suggestion marked as resolved successfully"}), 200

    except Exception as e:
        return jsonify({"message": f"Failed to mark as resolved: {str(e)}"}), 500

# Admin: Submit Feedback Route
@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    suggestion_id = data.get('suggestion_id')
    status = data.get('status')
    response = data.get('response')

    if not (suggestion_id and status and response):
        return jsonify({"message": "All fields are required"}), 400

    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Insert feedback into the FEEDBACK table (Admin_id will auto-increment)
        cursor.execute('''INSERT INTO FEEDBACK (Suggestion_id, Status, Response, Date_evaluated)
                  VALUES (%s, %s, %s, NOW())''', (suggestion_id, status, response))
        
        # Update suggestion status in the SUGGESTION table
        cursor.execute('''UPDATE SUGGESTION SET Status = %s WHERE Suggestion_id = %s''', (status, suggestion_id))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({"message": "Feedback submitted successfully"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/get_archived_suggestions', methods=['GET'])
def get_archived_suggestions():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM SUGGESTION WHERE Status = 'Resolved' ORDER BY Date_submitted DESC")
        suggestions = cursor.fetchall()
        cursor.close()
        return jsonify(suggestions), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Admin: Get Dashboard Data
@app.route('/get_admin_dashboard_data', methods=['GET'])
def get_admin_dashboard_data():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Count only Pending suggestions
        cursor.execute("SELECT COUNT(*) AS count FROM SUGGESTION WHERE Status = 'No Action Yet'")
        pending_count = cursor.fetchone()['count']

        # Fetch only latest 5 Pending suggestions
        cursor.execute("SELECT Suggestion_id, Message FROM SUGGESTION WHERE Status = 'No Action Yet' ORDER BY Date_submitted DESC LIMIT 5")
        recent_pending = cursor.fetchall()

        cursor.close()

        return jsonify({
            "No Action Yet": pending_count,
            "recentSuggestions": recent_pending
        }), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

# Student: View Feedback Route
@app.route('/get_student_feedback/<student_id>', methods=['GET'])
def get_student_feedback(student_id):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''SELECT S.Suggestion_id, C.Category_name, S.Message, S.Status, F.Response, F.Date_evaluated
                          FROM SUGGESTION S
                          LEFT JOIN CATEGORY C ON S.Category_id = C.Category_id
                          LEFT JOIN FEEDBACK F ON S.Suggestion_id = F.Suggestion_id
                          WHERE S.Student_id = %s''', (student_id,))
        
        feedbacks = cursor.fetchall()
        cursor.close()
        
        return jsonify(feedbacks), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
