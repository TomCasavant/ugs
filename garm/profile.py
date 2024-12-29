from typing import Dict

from flask import Blueprint, jsonify, request, redirect
from pydantic import BaseModel

from garm.db import get_db
from .activitypub.models.activity import Actor, PublicKey

bp = Blueprint('user', __name__, url_prefix='/')

# class PublicKey(BaseModel):
#     id: str
#     owner: str
#     public_key_pem: str = Field(alias='publicKeyPem')
class Profile(Actor):
    inbox: str
    outbox: str
    type: str
    name: str
    preferred_username: str
    summary: str
    discoverable: bool

    @classmethod
    def from_user_row(cls, user_row: dict) -> "Profile":
        # Use this method to create a Profile instance from the database row
        #public_key = PublicKey(
        #    id=user_row['steam_id'],
        #    owner=user_row['steam_id'],
        #    public_key_pem="test"
        #)
        # Get base URL from current webpage
        base_url = request.base_url.rsplit('/', 2)[0]
        base_url = base_url.replace('http:', 'https:')
        url = f"{base_url}/user/{user_row['steam_name']}"
        public_key = PublicKey.model_validate({
            'id': url + '#main-key',
            'owner': url,
            'publicKeyPem': user_row['public_key'].decode('utf-8')
        })

        actor = Actor.model_validate({
            'id': base_url + f"/user/{user_row['garm_id']}",
            'inbox': f"{base_url}/user/{user_row['steam_name']}/inbox",
            'outbox': f"{base_url}/user/{user_row['steam_name']}/outbox",
            'type': 'Person',
            'name': user_row['steam_name'],
            'preferredUsername': user_row['steam_name'],
            'summary': "Summary test",
            'discoverable': True,
            'publicKey': public_key,
            'icon': {
                'type': 'Image',
                'mediaType': 'image/jpeg',
                'url': user_row['profile_image']
            },
            'url': f"{base_url}/user/{user_row['steam_name']}",
            'manuallyApprovesFollowers': False,
            'attachment': [ {
                'type': 'PropertyValue',
                'name': 'Steam Profile',
                'value': f"<a href='{user_row['profile_url']}'>Steam Profile</a>"
            }],
            'published': user_row['created_at'],
            'alsoKnownAs': [user_row['profile_url']],
            'attributionDomains': [user_row['profile_url']]
        })
        return actor

# if GET then redirect to steam profile
# if POST then show json of user
@bp.route('/user/<username>', methods=['GET', 'POST'])
def user(username):
    db = get_db()
    user_row = db.execute(
        'SELECT * FROM actor WHERE steam_name = ?',
        (username,)
    ).fetchone()

    if user_row is None:
        # Check if matches /users/${garm_id}
        user_row = db.execute(
            'SELECT * FROM actor WHERE garm_id = ?',
            (username,)
        ).fetchone()

        # redirect if found
        if user_row is not None:
            return redirect(f"/user/{user_row['steam_name']}")

        return jsonify({'error': 'User not found'}), 404

    profile = Profile.from_user_row(user_row)
    model_dump = profile.model_dump(mode="json", by_alias=True)
    model_dump['@context'] = ['https://www.w3.org/ns/activitystreams', 'https://w3id.org/security/v1']

    if any(accept not in request.headers.get('Accept') for accept in ['application/activity+json', 'application/ld+json']):
        return redirect(user_row['profile_url'])

    response = jsonify(model_dump)
    response.headers['Content-Type'] = 'application/activity+json'
    return response