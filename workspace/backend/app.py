import os
import sys
import click
from random import randint

from application import create_app, db
from flask_migrate import Migrate

# for local auth:
from application.auth.v1.models import Permission, Role, User
# for delegated auth:
from application.auth.v2.models import DelegatedUser
from application.models import Post, PostFactory
from application.models import Follow

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
Migrate(app, db)

# coverage analysis engine:
cov = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage    
    cov = coverage.coverage(branch=True, include='application/*')    
    cov.start()

@app.shell_context_processor
def make_shell_context():
    # make extra variables available in flask shell context:    
    return dict(
        # database connector:
        db=db, 
        # authentication and authorization:
        # for local auth:
        Permission=Permission, Role=Role, User=User,
        # for delegated auth:
        DelegatedUser=DelegatedUser,
        # posts: 
        Post=Post, PostFactory=PostFactory
    )

@app.cli.command()
@click.option(
    '--coverage', default=False,
    help='Run tests under code coverage.'
)
def test(coverage):    
    """ Run the unit tests.
    """    
    # if coverage analysis is needed but the engine is not launched, re-run the command
    if coverage and not os.environ.get('FLASK_COVERAGE'):        
        os.environ['FLASK_COVERAGE'] = 'true'        
        os.execvp(sys.executable, [sys.executable] + sys.argv)    
    
    import unittest    
    
    tests = unittest.TestLoader().discover('tests')    
    unittest.TextTestRunner(verbosity=2).run(tests)    
    
    if cov:
        cov.stop()        
        cov.save()        
        # summary:
        print('Coverage Summary:')        
        cov.report()        
        # detailed report in HTML:
        basedir = os.path.abspath(os.path.dirname(__file__))        
        covdir = os.path.join(basedir, 'coverage')        
        cov.html_report(directory=covdir)        
        print('Detailed report in HTML is available at: file://%s/index.html' % covdir)
        # close:        
        cov.erase()

@app.cli.command()
def init_db_v1():
    """ Pop DB with initial data for local auth service
    """
    import json
    
    # init db:
    db.drop_all()
    db.create_all()
    
    # add users:
    success = False
    try:
        for user in accounts["users"]:
            # init user:
            user = User(**user)
            # set role:
            if user.username.startswith('user'):
                user.role_id = Role.query.filter(Role.name == 'user').first().id
            elif user.username.startswith('admin'):
                user.role_id = Role.query.filter(Role.name == 'admin').first().id
            # add to transaction:
            db.session.add(user)
        db.session.commit()
        success = True
    except:
        db.session.rollback()
        success=False
    finally:
        db.session.close()
    user_count = User.query.count()   
    print("[Init Users]: {} in total".format(user_count))

    # add posts:
    while Post.query.count() < 120:
        # in case the Faker creates a duplicated post:
        try:
            # random author selection:
            user = User.query.offset(
                randint(0, user_count - 1)
            ).first()
            # create post:
            post = PostFactory(author_id = user.id)
            db.session.add(post)
            db.session.commit()
        except:
            db.session.rollback()
    db.session.close()
    post_count = Post.query.count()   
    print("[Init Posts]: {} in total".format(post_count))

@app.cli.command()
def init_db_v2():
    """ Pop DB with initial data for delegated auth service
    """
    import json
    
    # init db:
    db.drop_all()
    db.create_all()
    
    # sycn users from backend:
    from application.auth.v2.services import Users
    service_user_management = Users()
    users = service_user_management.get()

    # add users:
    success = False
    try:
        for user in users:
            # init user:
            _, id = user['user_id'].split('|')
            user = DelegatedUser(
                id = id,
                email = user['email'],
                nickname = user['nickname']
            )
            # add to transaction:
            db.session.add(user)
        db.session.commit()
        success = True
    except:
        db.session.rollback()
        success=False
    finally:
        db.session.close()
    # get user summary:
    user_count = DelegatedUser.query.count()   
    print("\t[Init Users]: {} in total".format(user_count)) 

    # add posts:
    while Post.query.count() < 120:
        # in case the Faker creates a duplicated post:
        try:
            # random author selection:
            author = DelegatedUser.query.offset(
                randint(0, user_count - 1)
            ).first()
            # create post:
            post = PostFactory(author_id = author.id)
            db.session.add(post)
            db.session.commit()
        except:
            db.session.rollback()
    db.session.close()
    # get post summary:
    post_count = Post.query.count()   
    print("\t[Init Posts]: {} in total".format(post_count)) 

    # add follows:
    num_follows_per_user = user_count // 2 + 1
    for follower in DelegatedUser.query.all():
        for _ in range(num_follows_per_user):
            try:
                # generate followed:
                followed = DelegatedUser.query.offset(
                    randint(0, user_count - 1)
                ).first()
                
                # disable self following:
                if (follower.id != followed.id) and (not follower.is_following(followed)):
                    follower.follow(followed)
                    db.session.commit()
            except:
                db.session.rollback()
    db.session.close()
    # get post summary:
    follows_count = Follow.query.count()   
    print("\t[Init Follows]: {} in total".format(follows_count)) 

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)

    