from marshmallow import Schema, fields, validate


# Define the schema for input validation using Marshmallow
class PostSchema(Schema):
    title = fields.Str(required=True)
    content = fields.Dict(required=True)
    location = fields.Dict(required=True)
    tag = fields.Str(required=True, validate=validate.OneOf(['Positive', 'Neutral', 'Negative']))
    optionalTags = fields.List(fields.Str(), required=False, load_default=[]) # Make optional for backward compatibility
    captchaToken = fields.Str(required=True) # Add captcha token to schema
    createdAt = fields.DateTime()
    status = fields.Str(required=False, load_default='pending')

# Define a schema for tag validation
class TagSchema(Schema):
    tag = fields.Str(required=False, allow_none=True, validate=validate.OneOf(['Positive', 'Neutral', 'Negative']))
    optionalTags = fields.List(fields.Str(), required=False, load_default=[])