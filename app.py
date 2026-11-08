
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.security import check_password_hash
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "change-this-development-secret-key"


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("login.html")


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, full_name, email, password_hash, role
                FROM users
                WHERE email = %s
                """,
                (email,)
            )
            user = cursor.fetchone()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["full_name"] = user[1]
            session["role"] = user[4]
            return redirect(url_for("dashboard"))

        return "Invalid email or password.", 401

    finally:
        connection.close()


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("home"))

    role = session["role"]
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            # Update SLA status of unresolved tickets.
            cursor.execute(
                """
                UPDATE tickets
                SET sla_status = CASE
                    WHEN CURRENT_TIMESTAMP > sla_deadline
                    THEN 'overdue'
                    ELSE 'within_sla'
                END
                WHERE status IN ('open', 'in_progress')
                  AND sla_deadline IS NOT NULL
                """
            )

            # Update SLA status of resolved tickets.
            cursor.execute(
                """
                UPDATE tickets t
                SET sla_status = CASE
                    WHEN COALESCE(
                        (
                            SELECT h.changed_at
                            FROM ticket_history h
                            WHERE h.ticket_id = t.ticket_id
                              AND h.action_type = 'status_change'
                              AND h.new_status = 'resolved'
                            ORDER BY h.changed_at DESC, h.history_id DESC
                            LIMIT 1
                        ),
                        t.updated_at
                    ) <= t.sla_deadline
                    THEN 'completed_within_sla'
                    ELSE 'completed_late'
                END
                WHERE t.status IN ('resolved', 'closed')
                  AND t.sla_deadline IS NOT NULL
                """
            )

            # EMPLOYEE DASHBOARD
            if role == "employee":

                cursor.execute(
                    """
                    SELECT
                        t.ticket_id,
                        t.title,
                        t.category,
                        t.priority,
                        t.status,
                        t.created_at,
                        technician.full_name,
                        history.note
                    FROM tickets t
                    LEFT JOIN users technician
                        ON t.assigned_to = technician.user_id
                    LEFT JOIN LATERAL (
                        SELECT note
                        FROM ticket_history
                        WHERE ticket_id = t.ticket_id
                          AND new_status = 'resolved'
                          AND action_type = 'status_change'
                        ORDER BY changed_at DESC, history_id DESC
                        LIMIT 1
                    ) history ON TRUE
                    WHERE t.employee_id = %s
                    ORDER BY t.created_at DESC
                    """,
                    (session["user_id"],)
                )

                tickets = cursor.fetchall()
                connection.commit()

                return render_template(
                    "employee_dashboard.html",
                    tickets=tickets,
                    name=session["full_name"]
                )

            # ADMIN DASHBOARD
            elif role == "admin":

                cursor.execute(
                    """
                    SELECT
                        t.ticket_id,
                        t.title,
                        t.category,
                        t.priority,
                        t.status,
                        t.created_at,
                        employee.full_name,
                        technician.full_name,
                        t.assigned_to,
                        t.sla_deadline,
                        t.sla_status
                    FROM tickets t
                    JOIN users employee
                        ON t.employee_id = employee.user_id
                    LEFT JOIN users technician
                        ON t.assigned_to = technician.user_id
                    ORDER BY t.created_at DESC
                    """
                )

                tickets = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT user_id, full_name
                    FROM users
                    WHERE role = 'technician'
                    ORDER BY full_name
                    """
                )

                technicians = cursor.fetchall()

                # Fetch analytics data for the admin dashboard.
                cursor.execute(
                    """
                    SELECT
                        COUNT(*),
                        COUNT(*) FILTER (WHERE priority = 'high'),
                        COUNT(*) FILTER (WHERE priority = 'medium'),
                        COUNT(*) FILTER (WHERE priority = 'low'),
                        COUNT(*) FILTER (WHERE sla_status = 'overdue'),
                        COUNT(*) FILTER (WHERE status = 'in_progress')
                    FROM tickets
                    """
                )
                analytics = cursor.fetchone()

                connection.commit()

                return render_template(
                    "admin_dashboard.html",
                    tickets=tickets,
                    technicians=technicians,
                    analytics=analytics,
                    name=session["full_name"]
                )

            # TECHNICIAN DASHBOARD
            elif role == "technician":

                cursor.execute(
                    """
                    SELECT
                        t.ticket_id,
                        t.title,
                        t.description,
                        t.category,
                        t.priority,
                        t.status,
                        employee.full_name
                    FROM tickets t
                    JOIN users employee
                        ON t.employee_id = employee.user_id
                    WHERE t.assigned_to = %s
                    ORDER BY t.created_at DESC
                    """,
                    (session["user_id"],)
                )

                tickets = cursor.fetchall()
                connection.commit()

                return render_template(
                    "technician_dashboard.html",
                    tickets=tickets,
                    name=session["full_name"]
                )

            return "Invalid user role", 403

    except Exception:
        connection.rollback()
        app.logger.exception("Dashboard loading failed")
        return "Unable to load dashboard.", 500

    finally:
        connection.close()


# --------------------------------------------------
# CREATE TICKET WITH AUTOMATIC SLA
# --------------------------------------------------

@app.route("/create-ticket", methods=["POST"])
def create_ticket():

    if "user_id" not in session:
        return redirect(url_for("home"))

    if session["role"] != "employee":
        return "Access denied", 403

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "")
    priority = request.form.get("priority", "")

    if (
        not title
        or len(title) > 150
        or not description
        or category not in ["Hardware", "Software", "Network", "Other"]
        or priority not in ["low", "medium", "high"]
    ):
        return "Invalid ticket details.", 400

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            # Check for duplicate active tickets
            cursor.execute(
                """
                SELECT ticket_id, title
                FROM tickets
                WHERE employee_id = %s
                  AND LOWER(TRIM(title)) = LOWER(TRIM(%s))
                  AND status IN ('open', 'in_progress')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session["user_id"], title)
            )

            duplicate_ticket = cursor.fetchone()

            if duplicate_ticket:
                flash(
                    f"Similar active ticket already exists: #{duplicate_ticket[0]} - {duplicate_ticket[1]}",
                    "warning"
                )
                return redirect(url_for("dashboard"))

            # Calculate SLA deadline and create ticket
            cursor.execute(
                """
                INSERT INTO tickets
                    (
                        employee_id,
                        title,
                        description,
                        category,
                        priority,
                        sla_deadline,
                        sla_status
                    )
                VALUES (
                    %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP +
                    CASE
                        WHEN %s = 'high'
                            THEN INTERVAL '4 hours'
                        WHEN %s = 'medium'
                            THEN INTERVAL '8 hours'
                        WHEN %s = 'low'
                            THEN INTERVAL '24 hours'
                    END,
                    'within_sla'
                )
                RETURNING ticket_id
                """,
                (
                    session["user_id"],
                    title,
                    description,
                    category,
                    priority,
                    priority,
                    priority,
                    priority
                )
            )

            ticket_id = cursor.fetchone()[0]

            # Record ticket creation activity
            cursor.execute(
                """
                INSERT INTO ticket_history
                    (
                        ticket_id,
                        changed_by,
                        old_status,
                        new_status,
                        note,
                        action_type
                    )
                VALUES (%s, %s, NULL, %s, %s, %s)
                """,
                (
                    ticket_id,
                    session["user_id"],
                    "open",
                    "Ticket submitted by employee.",
                    "ticket_created"
                )
            )

        connection.commit()

        flash(
            f"Ticket #{ticket_id} submitted successfully!",
            "success"
        )

        return redirect(url_for("dashboard"))

    except Exception:
        connection.rollback()
        app.logger.exception("Ticket creation failed")
        return "Unable to submit ticket.", 500

    finally:
        connection.close()
# --------------------------------------------------
# ASSIGN TICKET AND RECORD ACTIVITY
# --------------------------------------------------

@app.route("/assign-ticket", methods=["POST"])
def assign_ticket():

    if "user_id" not in session:
        return redirect(url_for("home"))

    if session["role"] != "admin":
        return "Access denied. Admins only.", 403

    ticket_id = request.form.get("ticket_id", type=int)
    technician_id = request.form.get("technician_id", type=int)

    if not ticket_id or not technician_id:
        flash("Please select a valid ticket and technician.", "danger")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT full_name
                FROM users
                WHERE user_id = %s AND role = 'technician'
                """,
                (technician_id,)
            )

            technician = cursor.fetchone()

            if not technician:
                connection.rollback()
                flash("Selected user is not a valid technician.", "danger")
                return redirect(url_for("dashboard"))

            cursor.execute(
                """
                SELECT status, assigned_to
                FROM tickets
                WHERE ticket_id = %s
                FOR UPDATE
                """,
                (ticket_id,)
            )

            ticket = cursor.fetchone()

            if not ticket:
                connection.rollback()
                flash("Ticket not found.", "danger")
                return redirect(url_for("dashboard"))

            old_status = ticket[0]
            old_technician_id = ticket[1]

            cursor.execute(
                """
                UPDATE tickets
                SET assigned_to = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ticket_id = %s
                """,
                (technician_id, ticket_id)
            )

            # Record assignment only when it actually changes.
            if old_technician_id != technician_id:

                cursor.execute(
                    """
                    INSERT INTO ticket_history
                        (
                            ticket_id,
                            changed_by,
                            old_status,
                            new_status,
                            note,
                            action_type
                        )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ticket_id,
                        session["user_id"],
                        old_status,
                        old_status,
                        f"Assigned to {technician[0]}.",
                        "technician_assigned"
                    )
                )

        connection.commit()

        flash(
            f"Ticket #{ticket_id} assigned to {technician[0]} successfully!",
            "success"
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Ticket assignment failed")
        flash("Unable to assign the technician.", "danger")

    finally:
        connection.close()

    return redirect(url_for("dashboard"))


# --------------------------------------------------
# UPDATE TICKET STATUS AND SLA
# --------------------------------------------------

@app.route("/update-ticket-status", methods=["POST"])
def update_ticket_status():

    if "user_id" not in session:
        return redirect(url_for("home"))

    if session["role"] != "technician":
        return "Access denied. Technicians only.", 403

    ticket_id = request.form.get("ticket_id", type=int)
    new_status = request.form.get("new_status", "")
    note = request.form.get("note", "").strip()

    if not ticket_id or new_status not in ["in_progress", "resolved"]:
        flash("Invalid ticket or status.", "danger")
        return redirect(url_for("dashboard"))

    if new_status == "resolved" and not note:
        flash("Please enter a resolution note.", "danger")
        return redirect(url_for("dashboard"))

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT status
                FROM tickets
                WHERE ticket_id = %s AND assigned_to = %s
                FOR UPDATE
                """,
                (ticket_id, session["user_id"])
            )

            ticket = cursor.fetchone()

            if not ticket:
                connection.rollback()
                flash("Ticket not found or not assigned to you.", "danger")
                return redirect(url_for("dashboard"))

            old_status = ticket[0]

            allowed_transitions = {
                "open": "in_progress",
                "in_progress": "resolved"
            }

            if allowed_transitions.get(old_status) != new_status:
                connection.rollback()
                flash("This status change is not allowed.", "danger")
                return redirect(url_for("dashboard"))

            if new_status == "resolved":

                cursor.execute(
                    """
                    UPDATE tickets
                    SET status = %s,
                        updated_at = CURRENT_TIMESTAMP,
                        sla_status = CASE
                            WHEN CURRENT_TIMESTAMP <= sla_deadline
                                THEN 'completed_within_sla'
                            ELSE 'completed_late'
                        END
                    WHERE ticket_id = %s
                    """,
                    (new_status, ticket_id)
                )

            else:

                cursor.execute(
                    """
                    UPDATE tickets
                    SET status = %s,
                        updated_at = CURRENT_TIMESTAMP,
                        sla_status = CASE
                            WHEN CURRENT_TIMESTAMP > sla_deadline
                                THEN 'overdue'
                            ELSE 'within_sla'
                        END
                    WHERE ticket_id = %s
                    """,
                    (new_status, ticket_id)
                )

            # Record status activity.
            cursor.execute(
                """
                INSERT INTO ticket_history
                    (
                        ticket_id,
                        changed_by,
                        old_status,
                        new_status,
                        note,
                        action_type
                    )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    ticket_id,
                    session["user_id"],
                    old_status,
                    new_status,
                    note if note else "Technician started working.",
                    "status_change"
                )
            )

        connection.commit()

        flash(
            f"Ticket #{ticket_id} updated successfully!",
            "success"
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Ticket status update failed")
        flash("Unable to update ticket status.", "danger")

    finally:
        connection.close()

    return redirect(url_for("dashboard"))


# --------------------------------------------------
# CHECK WHETHER USER CAN ACCESS A TICKET
# --------------------------------------------------

def get_accessible_ticket(cursor, ticket_id):

    role = session.get("role")
    user_id = session.get("user_id")

    if role == "employee":
        access_condition = "AND t.employee_id = %s"
        parameters = (ticket_id, user_id)

    elif role == "technician":
        access_condition = "AND t.assigned_to = %s"
        parameters = (ticket_id, user_id)

    elif role == "admin":
        access_condition = ""
        parameters = (ticket_id,)

    else:
        return None

    cursor.execute(
        f"""
        SELECT
            t.ticket_id,
            t.title,
            t.description,
            t.category,
            t.priority,
            t.status,
            employee.full_name,
            technician.full_name,
            t.created_at
        FROM tickets t
        JOIN users employee
            ON t.employee_id = employee.user_id
        LEFT JOIN users technician
            ON t.assigned_to = technician.user_id
        WHERE t.ticket_id = %s
        {access_condition}
        """,
        parameters
    )

    return cursor.fetchone()


# --------------------------------------------------
# VIEW TICKET DETAILS, COMMENTS AND ACTIVITY
# --------------------------------------------------

@app.route("/ticket/<int:ticket_id>")
def ticket_details(ticket_id):

    if "user_id" not in session:
        return redirect(url_for("home"))

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            ticket = get_accessible_ticket(cursor, ticket_id)

            if not ticket:
                return "Ticket not found or access denied.", 404

            # Fetch comments and replies.
            cursor.execute(
                """
                SELECT
                    c.comment_id,
                    c.parent_comment_id,
                    u.full_name,
                    u.role,
                    c.comment_text,
                    c.created_at
                FROM comments c
                JOIN users u
                    ON c.user_id = u.user_id
                WHERE c.ticket_id = %s
                ORDER BY c.created_at ASC, c.comment_id ASC
                """,
                (ticket_id,)
            )

            all_comments = cursor.fetchall()

            comments_by_id = {}

            for comment in all_comments:
                comments_by_id[comment[0]] = {
                    "comment_id": comment[0],
                    "parent_comment_id": comment[1],
                    "full_name": comment[2],
                    "role": comment[3],
                    "comment_text": comment[4],
                    "created_at": comment[5],
                    "replies": []
                }

            original_comments = []

            for comment in comments_by_id.values():

                if comment["parent_comment_id"] is None:
                    original_comments.append(comment)

                else:
                    parent = comments_by_id.get(
                        comment["parent_comment_id"]
                    )

                    if parent:
                        parent["replies"].append(comment)

            # Fetch ticket activity history.
            cursor.execute(
                """
                SELECT
                    h.history_id,
                    h.action_type,
                    h.old_status,
                    h.new_status,
                    h.note,
                    h.changed_at,
                    u.full_name,
                    u.role
                FROM ticket_history h
                JOIN users u
                    ON h.changed_by = u.user_id
                WHERE h.ticket_id = %s
                ORDER BY h.changed_at ASC, h.history_id ASC
                """,
                (ticket_id,)
            )

            activities = cursor.fetchall()

        return render_template(
            "ticket_details.html",
            ticket=ticket,
            comments=original_comments,
            activities=activities,
            back_url="dashboard",
            name=session["full_name"]
        )

    finally:
        connection.close()


# --------------------------------------------------
# ADD A NEW COMMENT OR REPLY
# --------------------------------------------------

@app.route("/ticket/<int:ticket_id>/comment", methods=["POST"])
def add_comment(ticket_id):

    if "user_id" not in session:
        return redirect(url_for("home"))

    comment_text = request.form.get("comment_text", "").strip()

    parent_comment_id = request.form.get(
        "parent_comment_id",
        type=int
    )

    if not comment_text or len(comment_text) > 2000:
        flash(
            "Comment must contain between 1 and 2000 characters.",
            "danger"
        )

        return redirect(
            url_for("ticket_details", ticket_id=ticket_id)
        )

    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:

            ticket = get_accessible_ticket(cursor, ticket_id)

            if not ticket:
                connection.rollback()
                return "Ticket not found or access denied.", 404

            # Verify the parent comment belongs to this ticket.
            if parent_comment_id is not None:

                cursor.execute(
                    """
                    SELECT comment_id
                    FROM comments
                    WHERE comment_id = %s
                      AND ticket_id = %s
                      AND parent_comment_id IS NULL
                    """,
                    (parent_comment_id, ticket_id)
                )

                parent = cursor.fetchone()

                if not parent:
                    connection.rollback()

                    flash(
                        "Invalid comment selected for reply.",
                        "danger"
                    )

                    return redirect(
                        url_for("ticket_details", ticket_id=ticket_id)
                    )

            cursor.execute(
                """
                INSERT INTO comments
                    (ticket_id, user_id, comment_text, parent_comment_id)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    ticket_id,
                    session["user_id"],
                    comment_text,
                    parent_comment_id
                )
            )

        connection.commit()

        if parent_comment_id is not None:
            flash("Your reply was posted successfully!", "success")
        else:
            flash("Your comment was posted successfully!", "success")

    except Exception:
        connection.rollback()
        app.logger.exception("Comment submission failed")
        flash("Unable to post your comment.", "danger")

    finally:
        connection.close()

    return redirect(
        url_for("ticket_details", ticket_id=ticket_id)
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
