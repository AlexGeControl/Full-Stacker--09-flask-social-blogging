from application import db
from application.auth.v1.models import User
from application.models import Post

from flask import current_app
from flask import abort, request, flash, render_template, redirect, url_for
# auth v1:
from flask_login import login_required, current_user
# auth v2:
from application.auth.v2.decorators import requires_auth

from . import bp

from .forms import PostForm

from datetime import datetime

#  CREATE
#  ----------------------------------------------------------------
@bp.route('/create', methods=['GET', 'POST'])
# for local auth:
# @login_required
# for delegated auth:
@requires_auth
def create_post():
    """ render empty form for new post creation
    """
    if request.method == 'GET':
        # create empty form:
        form = PostForm()
    if request.method == 'POST': 
        # init form with POSTed form:
        form = PostForm(request.form)

        if form.validate():        
            try:
                # create new post:
                id = Post.query.count() + 1

                post = Post(
                    id = id,
                    title = form.title.data,
                    contents = form.contents.data,
                    author = current_user._get_current_object()
                )
                # insert:
                db.session.add(post)
                # write
                db.session.commit()
                # on successful registration, flash success
                flash('Post was successfully updated.')
                return redirect(url_for('posts.posts'))
            except:
                db.session.rollback()
                # on unsuccessful registration, flash an error instead.
                flash('An error occurred. Post could not be updated.')
            finally:
                db.session.close()
        else:
            # for debugging only:
            flash(form.errors)
            pass
            
    return render_template('posts/forms/post.html', form=form)

#  READ
#  ----------------------------------------------------------------
@bp.route('/', methods=['GET'])
def posts():
    """ show all posts
    """
    # parse query parameter page:
    page = request.args.get('page', 1, type=int)

    # data:
    user_subq = User.query.with_entities(
        User.id,
        User.username
    ).subquery()

    # generate pagination:
    pagination = Post.query.with_entities(
        Post.id,
        Post.title,
        user_subq.c.username.label("author"),
        Post.timestamp
    ).join(
        user_subq, Post.author_id == user_subq.c.id
    ).order_by(
        Post.timestamp.desc()
    ).paginate(
        page, per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )
    posts = pagination.items
    
    # format:
    posts=[
        {
            "id": id,
            "title": title,
            "author": author,
            "timestamp": timestamp,
        } for (id, title, author, timestamp) in posts
    ]
    
    return render_template('posts/pages/posts.html', posts=posts, pagination=pagination)

@bp.route('/<int:post_id>')
# for local auth:
# @login_required
# for delegated auth:
@requires_auth
def show_post(post_id):
    """ show given post
    """
    # data:
    user_subq = User.query.with_entities(
        User.id,
        User.username
    ).subquery()

    posts = Post.query.with_entities(
        Post.id,
        Post.title,
        user_subq.c.username.label("author"),
        Post.timestamp,
        Post.contents,
        Post.contents_html
    ).filter(
        Post.id == post_id
    ).join(
        user_subq, Post.author_id == user_subq.c.id
    ).all()

    if len(posts) == 0:
        abort(
            404, 
            description='There is no post with id={}'.format(post_id)
        )

    # format:
    (id, title, author, timestamp, contents, contents_html) = posts[0]

    post = {
        "id": id,
        "title": title,
        "author": author,
        "timestamp": timestamp,
        "contents": contents,
        "contents_html": contents_html
    }

    return render_template('posts/pages/post.html', post=post)

#  UPDATE
#  ----------------------------------------------------------------
@bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
# for local auth:
# @login_required
# for delegated auth:
@requires_auth
def edit_post(post_id):
    """ render form pre-filled with given post
    """
    # select post:
    post = Post.query.get_or_404(
        post_id, 
        description='There is no post with id={}'.format(post_id)
    )

    if request.method == 'GET':
        # init form with selected post:
        post = post.to_json()
        form = PostForm(
            title = post["title"], 
            contents = post["contents"]
        )
    if request.method == 'POST': 
        # init form with POSTed form:
        form = PostForm(request.form)

        if form.validate():        
            try:
                # update post:
                post.title = form.title.data
                post.contents = form.contents.data
                post.timestamp = datetime.utcnow()
                # insert:
                db.session.add(post)
                # write
                db.session.commit()
                # on successful registration, flash success
                flash('Post was successfully updated.')
                return redirect(url_for('posts.posts'))
            except:
                db.session.rollback()
                # on unsuccessful registration, flash an error instead.
                flash('An error occurred. Post could not be updated.')
            finally:
                db.session.close()
        else:
            # for debugging only:
            flash(form.errors)
            pass
            
    return render_template('posts/forms/post.html', form=form, post=post)

#  DELETE
#  ----------------------------------------------------------------
@bp.route('/<int:post_id>', methods=['DELETE'])
# for local auth:
# @login_required
# for delegated auth:
@requires_auth
def delete_post(post_id):
    """ delete post
    """
    error = True

    try:
        # find:
        post = Post.query.get_or_404(
            post_id, 
            description='There is no post with id={}'.format(post_id)
        )
        db.session.delete(post)
        # write
        db.session.commit()
        # on successful db insert, flash success
        flash('Post was successfully deleted!')
        error = False
    except:
        db.session.rollback()
        # on unsuccessful db insert, flash an error instead.
        flash('An error occurred. Post could not be deleted.')
        error = True
    finally:
        db.session.close()

    if error:
        abort(400)

    return redirect(url_for('posts.posts'))
