from app.extensions import mongo


def get_posts_collection():
    return mongo.db.stories

def get_users_collection():
    return mongo.db.users

def get_tags_collection():
    return mongo.db.approved_tags
