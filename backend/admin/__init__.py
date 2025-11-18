from flask import redirect, session, url_for
from flask_admin import Admin
from flask_admin.base import AdminIndexView, expose

from app.extensions import admin
from repos.repos import get_posts_collection, get_tags_collection, get_users_collection

from .views import PostView, UserView


def init_admin(app):
    class ProtectedAdminIndexView(AdminIndexView):
        def is_accessible(self):
            # Allow access to admin and moderator users
            try:
                return ('user' in session and 
                        session['user'] is not None and 
                        isinstance(session['user'], dict) and 
                        session['user'].get('role') in ['admin', 'moderator'])
            except (KeyError, AttributeError, TypeError):
                return False

        def inaccessible_callback(self, name, **kwargs):
            try:
                return redirect(url_for('login'))
            except Exception:
                from flask import abort
                abort(403)

        @expose('/')
        def index(self):
            return redirect(url_for('postview.index_view'))  # Redirect to PostView by default

    # Initialize admin with the custom index view
    admin._set_admin_index_view(ProtectedAdminIndexView())
    admin.init_app(app)
    # Add PostView and UserView
    POSTS = get_posts_collection()
    USERS = get_users_collection()
    admin.add_view(PostView(POSTS, 'Posts', endpoint='postview'))
    admin.add_view(UserView(USERS, 'Users', endpoint='userview'))  # Pass user_collection here

    return admin