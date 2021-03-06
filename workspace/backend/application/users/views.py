from datetime import datetime

from application import db
from application.auth.v2.models import DelegatedUser
from application.models import Follow, Post

from flask import current_app
from flask import session
from application.auth.v2.session import Session
from application.auth.v2.decorators import requires_auth
from flask import abort, request, flash, render_template, redirect, url_for

from . import bp
from . import service_user_by_email, service_user_management
from .forms import ProfileForm
from application.auth.v2.models import DelegatedUser

#  READ
#  ----------------------------------------------------------------
@bp.route('/<user_id>')
# for local auth:
# @login_required
# for delegated auth:
@requires_auth
def show_user(user_id):
    """ show user profile
    """
    # fetch current user:
    current_user = DelegatedUser.query.get(session[Session.ID])

    # fetch the specified user's profile from backend:
    selected_user = DelegatedUser.query.filter(
        DelegatedUser.id == user_id
    ).first()
    userinfo = service_user_by_email.get(selected_user.email)[0]
    
    # user profile display:
    _, id = userinfo['user_id'].split('|')
    user = {
        "id": id,
        "nickname": userinfo["nickname"],
        "location": userinfo["user_metadata"]["location"] if ("user_metadata" in userinfo and "location" in userinfo["user_metadata"]) else "",
        "about_me": userinfo["user_metadata"]["about_me"] if ("user_metadata" in userinfo and "about_me" in userinfo["user_metadata"]) else "",
        "last_updated": datetime.strptime(
            userinfo["updated_at"], 
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
        "last_seen": datetime.strptime(
            userinfo["last_login"], 
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
        "is_the_same_user": session[Session.ID] == user_id,
        "is_following": current_user.is_following(selected_user),
        "num_followers": Follow.query.filter(Follow.followed_id == user_id).count(),
        "num_followed": Follow.query.filter(Follow.follower_id == user_id).count(),
    }

    # fetch latest posts:
    posts = Post.query.with_entities(
        Post.uuid,
        Post.title,
        Post.timestamp
    ).filter(
        Post.author_id == id
    ).order_by(
        Post.timestamp.desc()
    ).limit(
        10
    ).all()
    
    # format:
    posts=[
        {
            "id": id.hex,
            "title": title,
            "timestamp": timestamp,
        } for (id, title, timestamp) in posts
    ]

    return render_template('users/pages/user.html', user=user, posts=posts)

#  UPDATE
#  ----------------------------------------------------------------
@bp.route('/<user_id>/edit', methods=['GET', 'POST'])
# for local auth:
# @login_required
# for delegated auth:
@requires_auth
def edit_user(user_id):
    """ render form pre-filled with given user
    """
    if request.method == 'GET':
        # init form with current user:
        form = ProfileForm(
            nickname = session[Session.PROFILE]["nickname"], 
            location = session[Session.PROFILE]["location"],
            about_me = session[Session.PROFILE]["about_me"]
        )
    if request.method == 'POST': 
        # init form with POSTed form:
        form = ProfileForm(request.form)

        if form.validate():                       
            # update backend:
            response = service_user_management.patch(
                id = f'auth0|{user_id}', 
                nickname = form.nickname.data, 
                location = form.location.data,
                about_me = form.about_me.data
            )

            # success:
            if 'identities' in response:         
                try:
                    # update db:
                    delegated_user = DelegatedUser.query.get_or_404(
                        user_id, 
                        description='There is no user with id={}'.format(user_id)
                    )
                    delegated_user.nickname = form.nickname.data
                    # update:
                    db.session.add(delegated_user)
                    # write
                    db.session.commit()

                    # update session:
                    session[Session.PROFILE]["nickname"] = form.nickname.data
                    session[Session.PROFILE]["location"] = form.location.data
                    session[Session.PROFILE]["about_me"] = form.about_me.data
                    
                    # on successful profile update, flash success
                    flash('Your profile was successfully updated.')

                    return redirect(url_for('.show_user', user_id = user_id))
                except:
                    db.session.rollback()
                    # on unsuccessful registration, flash an error instead.
                    flash('An error occurred. New account could not be created.')
                finally:
                    db.session.close()
            # failure:
            else:
                flash(response['message'])                
        else:
            # for debugging only:
            flash(form.errors)
            
    return render_template('users/forms/user.html', form=form, user_id=user_id)
