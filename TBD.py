import sys
sys.path.append('./lib')
import logging
import logging.config
import argparse
import os
from flask import Flask, request, render_template
from flask.ext.bootstrap import Bootstrap
from flask.ext.script import Manager
from flask.ext.wtf import Form
from flask.ext.sqlalchemy import SQLAlchemy
from wtforms import StringField, SubmitField
from wtforms.validators import Required

VERSION='0.2.1'
"""
0.0.1
    1. 

"""
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'console_format': {
            'format': '%(levelname)s %(name)s %(lineno)d %(message)s'
        },
        'file_format': {
            'format': '%(asctime)s %(levelname)s %(name)s %(lineno)d %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'console_format',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'twisted': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

log = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 't_span123'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db', 'mdm_tbd.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

log.debug("Initialize Flask App instance {}!".format(app))

db = SQLAlchemy(app)
bootstrap = Bootstrap(app)
manager = Manager(app)

def config_log(opts):
    loglevel = getattr(logging, opts.get('level').upper(), None)
    if not isinstance(loglevel, int):
        raise ValueError("Invalid log level: {!r}".format(opts.get('level')))
    if opts.get('file', None):
        LOGGING['handlers']['file'] = {
            'level': 'DEBUG', #File log should always be completed
            'class': 'logging.FileHandler',
            'formatter': 'file_format',
            'filename': opts['file'],
            'mode': 'w',
        }
        LOGGING['root']['handlers'].append('file')
    LOGGING['handlers']['console']['level'] = loglevel #Console log can be adjusted by command line
    logging.config.dictConfig(LOGGING)
    
class TD(db.Model):
    __tablename__ = 'td'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    host_id = db.Column(db.Integer, db.ForeignKey('hosts.id'))
    build_id = db.Column(db.Integer, db.ForeignKey('builds.id'))
    tc_name = db.Column(db.String(64), nullable=False)
    __table_args__ = (
        db.UniqueConstraint(host_id, build_id, tc_name, name='unique_tc_build_and_host'),
    )
    
    test_client = db.Column(db.String(64), nullable=False)
    crash_num = db.Column(db.Integer, default=0)
    ta_name = db.Column(db.String(64), nullable=True)
    tc_result = db.Column(db.Boolean, nullable=True)
    ta_result = db.Column(db.Boolean, nullable=True)
    
    def __repr__(self):
        return '<TD {}>'.format(self.host_name)
        
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    td = db.relationship(TD, backref='project')
    
    def __repr__(self):
        return '<Project {}>'.format(self.name)
        
class Host(db.Model):
    __tablename__ = 'hosts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    ip_addr = db.Column(db.String(64), nullable=False)
    td = db.relationship(TD, backref='host')
    
    def __repr__(self):
        return '<Host {}>'.format(self.name)
        
class Build(db.Model):
    __tablename__ = 'builds'
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.TEXT, unique=True)
    td = db.relationship(TD, backref='build')
    
    def __repr__(self):
        return '<Build {}>'.format(self.version)
        

        
@app.route('/')
def index():
    return render_template('base.html', name = 'lpei')
    
@app.route('/mdm')
def mdm():
    form = TestDataForm()
    for k in form.__dict__:
        k_o = getattr(form, k)
        log.debug("form key {}: {}".format(k, callable(k_o)))
    return render_template('mdm.html', form = form, getattr = getattr, callable = callable)

def str2bool(val):
    r = None
    if len(val):
        if val.upper() == 'PASS':
            r = True
        else:
            r = False
    return r
    
def str2int(val):
    r = 0
    if len(val):
        try:
            r = int(val)
        except Exception:
            print "Failed to transfer {} to integer!".format(val)
    return r
    
@app.route('/mdm/td', methods=['GET', 'POST'])
def mdm_td():
    form = TestDataForm(csrf_enabled=False)
    for field in form:
        log.debug("Get field {}={}!".format(field.name, field.data))
    if form.validate_on_submit():
        log.debug("Get validate table!")
        project_name = form.project_name.data
        host_name = form.host_name.data
        ip_addr = form.ip_addr.data
        build_version = form.build_verion.data
        tc_name = form.tc_name.data
        test_client = form.test_client.data
        ta_name = form.ta_name.data
        tc_result = str2bool(form.tc_result.data)
        ta_result = str2bool(form.ta_result.data)
        crash_num = str2int(form.is_crash.data)

        project = Project.query.filter_by(name=project_name).first()
        if not project:
            project = Project(name=project_name)
            db.session.add(project)
            
        host = Host.query.filter_by(name=host_name).first()
        if host:
            host.ip_addr = ip_addr
        else:
            host = Host(name=host_name, ip_addr=ip_addr)
        db.session.add(host)
            
        build = Build.query.filter_by(version=build_version).first()
        if not build:
            build = Build(version=build_version)
            db.session.add(build)
        
        td = TD.query.filter_by(tc_name=tc_name).filter_by(build=build).filter_by(host=host).first()
        if td:
            td.crash_num += crash_num
            td.test_client=test_client
            td.ta_name=ta_name
            td.tc_result=tc_result
            td.ta_result=ta_result
        else:
            td = TD(project=project, host=host, build=build, tc_name=tc_name, crash_num=crash_num,
                    test_client=test_client, ta_name=ta_name, tc_result=tc_result, ta_result=ta_result)
        db.session.add(td)
            
        db.session.commit()
    else:
        log.debug("No validate table!")
        return render_template('mdm_td.html', form = form), 400
    return render_template('mdm_td.html', form = form)

@app.route('/mdm/tbd', methods=['GET'])
def mdm_tbd():
    tbd = TD.query.all()
    return render_template('mdm_tbd.html', tbd = tbd)

class TestDataForm(Form):
    project_name = StringField('Project name?', validators=[Required()])
    host_name = StringField('Host name?', validators=[Required()])
    ip_addr = StringField('IP address?', validators=[Required()])
    tc_name = StringField('Test case name?', validators=[Required()])
    test_client = StringField('Test client name and version?', validators=[Required()])
    build_verion = StringField('Build version?', validators=[Required()])
    is_crash = StringField('Is Crash?', validators=[])
    tc_result = StringField('Test case result, pass or fail or None?', validators=[])
    ta_name = StringField('Test action name?', validators=[])
    ta_result = StringField('Test action result, pass or fail or None?', validators=[])
    
    submit = SubmitField("Submit") 
    
if __name__ == '__main__':
    # opts = args_option()
    # log.debug("Start app at port {}!".format(opts.port))
    config_log({'level': 'debug'})
    db.create_all()
    manager.run()


    
    

