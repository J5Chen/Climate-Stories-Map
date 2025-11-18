from flask_admin import Admin
from flask_cors import CORS
from flask_pymongo import PyMongo

mongo = PyMongo()
admin = Admin(
        name='Climate Stories Map',
        template_mode='bootstrap4',
        base_template='admin/master.html',
    )
cors = CORS()