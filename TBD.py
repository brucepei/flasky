import sys
sys.path.append('./lib')
import logging
import logging.config
import argparse
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask.ext.bootstrap import Bootstrap
from flask.ext.script import Manager
from flask.ext.wtf import Form
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.migrate import Migrate, MigrateCommand
from wtforms import HiddenField, StringField, SubmitField
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db', 'tdb.sqlite')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

log.debug("Initialize Flask App instance {}!".format(app))

db = SQLAlchemy(app)
bootstrap = Bootstrap(app)
manager = Manager(app)
migrate = Migrate(app, db)
manager.add_command('db', MigrateCommand)

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
    
def str2bool(val):
    r = None
    if len(val):
        val_lower = val.lower()
        if val_lower == 'fail' or val_lower == 'no' or val_lower == 'nok' or val_lower == '0':
            r = False
        else:
            r = True
    return r
    
def str2int(val):
    r = 0
    if len(val):
        try:
            r = int(val)
        except Exception:
            print "Failed to transfer {} to integer!".format(val)
    return r

class TD(db.Model):
    __tablename__ = 'td'

    id = db.Column(db.Integer, primary_key=True)
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
    update_time = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return '<TD {}>'.format(self.host_name)
        
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    build = db.relationship('Build', backref='project')
    
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
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    version = db.Column(db.TEXT, unique=True)
    name = db.Column(db.String(64), nullable=False)
    meta_path = db.Column(db.TEXT, nullable=False)
    local_path = db.Column(db.TEXT, nullable=True)
    crash_path = db.Column(db.TEXT, nullable=False)
    is_crm = db.Column(db.Boolean, nullable=True)
    td = db.relationship(TD, backref='build')
    
    def __repr__(self):
        return '<Build {}>'.format(self.version)

    
class TestDataForm(Form):
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
    delete = SubmitField("Delete")
    
class BuildForm(Form):
    project_name = HiddenField('Project name?', validators=[Required()])
    version = StringField('Build version?', validators=[Required()])
    name = StringField('Build short name?', validators=[Required()])
    meta_path = StringField('Meta path?', validators=[Required()])
    local_path = StringField('Local build path?', validators=[])
    crash_path = StringField('Crash path?', validators=[Required()])
    is_crm = StringField('Is CRM build?', validators=[])
    submit = SubmitField("Submit")
    delete = SubmitField("Delete")

class ProjectForm(Form):
    name = StringField('Project name?', validators=[Required()])
    submit = SubmitField("Submit")
    delete = SubmitField("Delete")
    
@app.route('/')
def index():
    project = Project.query.order_by(Project.name).all()
    return render_template('base.html', project=project)

@app.route('/build/list', methods=['GET', 'POST'])
def build_list():
    project = Project.query.order_by(Project.name).all()
    project_name = request.args.get('project_name', None)
    if project_name:
        builds = Build.query.join(Build.project).filter(Project.name==project_name).order_by(db.desc(Build.version)).all()
    else:
        builds = Build.query.order_by(db.desc(Build.version)).all()
    if request.method == 'POST':
        build_list = []
        for build in builds:
            build_list.append({'version': build.version, 'name': build.name, 'meta_path': build.meta_path, 'local_path': build.local_path, 'crash_path': build.crash_path, 'is_crm': build.is_crm})
        return jsonify(code=0, result=build_list)
    else:
        return render_template('build_list.html', project=project, project_name=project_name, builds=builds)

@app.route('/project/tbd', methods=['GET'])
def project_tbd():
    project = Project.query.order_by(Project.name).all()
    project_name = request.args.get('project_name', None)
    build_version = request.args.get('build_version', None)
    log.debug("Query TBD for project {} and build {}!".format(project_name, build_version))
    if build_version:
        tbd = TD.query.join(TD.host).join(TD.build).join(Build.project).filter(Build.version==build_version).order_by(Host.ip_addr).all()
    elif project_name:
        tbd = TD.query.join(TD.host).join(TD.build).join(Build.project).filter(Project.name==project_name).order_by(Host.ip_addr).all()
    else:
        tbd = TD.query.join(TD.host).join(TD.build).join(Build.project).order_by(Host.ip_addr).all()
    return render_template('project_tbd.html', project=project, project_name=project_name, tbd=tbd)

@app.route('/manual/build')
def manual_build():
    project = Project.query.order_by(Project.name).all()
    project_name = request.args.get('project_name', None)
    form = BuildForm(project_name=project_name)
    for k in form.__dict__:
        k_o = getattr(form, k)
        log.debug("form key {}: {}".format(k, callable(k_o)))
    return render_template('manual_build.html', project=project, form=form, project_name=project_name)

@app.route('/manual/test')
def manual_test():
    project = Project.query.order_by(Project.name).all()
    project_name = request.args.get('project_name', None)
    form = TestDataForm(project_name=project_name)
    for k in form.__dict__:
        k_o = getattr(form, k)
        log.debug("form key {}: {}".format(k, callable(k_o)))
    return render_template('manual_test.html', project=project, project_name=project_name, form=form)
    
@app.route('/manual/project')
def manual_project():
    project = Project.query.order_by(Project.name).all()
    form = ProjectForm()
    for k in form.__dict__:
        k_o = getattr(form, k)
        log.debug("form key {}: {}".format(k, callable(k_o)))
    return render_template('manual_project.html', project=project, form=form)

@app.route('/project/new', methods=['POST'])
def project_new():
    form = ProjectForm()
    for field in form:
        log.debug("Get project field {}={}!".format(field.name, field.data))
    if form.validate_on_submit():
        log.debug("Get validate build table!")
        name = form.name.data
        is_delete = form.delete.data

        if is_delete:
            project = Project.query.filter_by(name=name).first()
            if project:
                project_builds = Build.query.filter_by(project=project).all()
                if project_builds:
                    log.debug("Project {} are used by build, so cannot delete!".format(name))
                    return jsonify(code=-1, result="Project {} are used by build, so cannot delete!".format(name)), 400
                else:
                    db.session.delete(project)
                    db.session.commit()
                    return jsonify(code=0, result="delete ok")
            else:
                log.debug("No matched project {}, cannot delete!".format(name))
                return jsonify(code=-1, result="No matched project {}, cannot delete!".format(name)), 400
            
            
        project = Project.query.filter_by(name=name).first()
        if project:
            return jsonify(code=0, result="already exists!")
        else:
            project = Project(name=name)
            db.session.add(project)
            db.session.commit()
    else:
        log.debug("No validate build table!")
        return jsonify(code=-1, result="no validate build table"), 400
    return jsonify(code=0, result="ok")

@app.route('/project/build', methods=['POST'])
def project_build():
    form = BuildForm()
    for field in form:
        log.debug("Get build field {}={}!".format(field.name, field.data))
    if form.validate_on_submit():
        log.debug("Get validate build table!")
        version = form.version.data
        name = form.name.data
        project_name = form.project_name.data
        meta_path = form.meta_path.data
        local_path = form.local_path.data
        crash_path = form.crash_path.data
        is_crm = str2bool(form.is_crm.data)
        
        is_delete = form.delete.data

        if is_delete:
            build = Build.query.filter_by(version=version).first()
            if build:
                build_tds = TD.query.filter_by(build=build).all()
                if build_tds:
                    log.debug("build {} are used by td, so cannot delete!".format(version))
                    return jsonify(code=-1, result="build {} are used by td, so cannot delete!".format(version)), 400
                else:
                    db.session.delete(build)
                    db.session.commit()
                    return jsonify(code=0, result="delete ok")
            else:
                log.debug("No matched build {}, cannot delete!".format(version))
                return jsonify(code=-1, result="No matched build {}, cannot delete!".format(version)), 400
            
        project = Project.query.filter_by(name=project_name).first()
        if not project:
            if is_delete:
                log.debug("Not exists project {} when delete {}!".format(project_name, build_version))
                return jsonify(code=-1, result="Not exists project {} when delete {}!".format(project_name, build_version)), 400
            project = Project(name=project_name)
            db.session.add(project)
            
        build = Build.query.filter_by(version=version).first()
        if build:
            build.name = name
            build.project = project
            build.meta_path = meta_path
            build.local_path = local_path
            build.crash_path = crash_path
            build.is_crm = is_crm
        else:
            build = Build(version=version, project=project, name=name, 
                            meta_path=meta_path, local_path=local_path, crash_path=crash_path, is_crm=is_crm)
        db.session.add(build)
            
        db.session.commit()
    else:
        log.debug("No validate build table!")
        return jsonify(code=-1, result="no validate build table"), 400
    return jsonify(code=0, result="ok")

@app.route('/project/td', methods=['POST'])
def project_td():
    form = TestDataForm(csrf_enabled=False)
    for field in form:
        log.debug("Get test data field {}={}!".format(field.name, field.data))
    if form.validate_on_submit():
        log.debug("Get validate test data table!")
        host_name = form.host_name.data
        ip_addr = form.ip_addr.data
        build_version = form.build_verion.data
        tc_name = form.tc_name.data
        test_client = form.test_client.data
        ta_name = form.ta_name.data
        tc_result = str2bool(form.tc_result.data)
        ta_result = str2bool(form.ta_result.data)
        crash_num = str2int(form.is_crash.data)
        
        is_delete = form.delete.data

        build = Build.query.filter_by(version=build_version).first()
        if not build:
            log.debug("Not exists build {}!".format(build_version))
            return jsonify(code=-1, result="Not exists build {}!".format(build_version)), 400
            
        host = Host.query.filter_by(name=host_name).first()
        if host:
            host.ip_addr = ip_addr
        else:
            if is_delete:
                log.debug("Not exists host {} when delete {}!".format(host_name, build_version))
                return jsonify(code=-1, result="Not exists host {} when delete {}!".format(host_name, build_version)), 400
            host = Host(name=host_name, ip_addr=ip_addr)
        db.session.add(host)

        if is_delete:
            td = TD.query.filter_by(tc_name=tc_name).filter_by(build=build).filter_by(host=host).first()
            if td:
                host_tds = TD.query.filter_by(host=host).all()
                if host_tds and len(host_tds) == 1:
                    log.debug("Only 1 host left, so also delete host {}!".format(host_name))
                    db.session.delete(host)
                db.session.delete(td)
                db.session.commit()
                return jsonify(code=0, result="delete ok")
            return jsonify(code=-1, result="not exists record, cannot delete!"), 400
            
        td = TD.query.filter_by(tc_name=tc_name).filter_by(build=build).filter_by(host=host).first()
        if td:
            td.crash_num += crash_num
            td.test_client=test_client
            td.ta_name=ta_name
            td.tc_result=tc_result
            td.ta_result=ta_result
        else:
            td = TD(host=host, build=build, tc_name=tc_name, crash_num=crash_num,
                    test_client=test_client, ta_name=ta_name, tc_result=tc_result, ta_result=ta_result)
        td.update_time = datetime.now()
        db.session.add(td)
            
        db.session.commit()
    else:
        log.debug("No validate test data table!")
        return jsonify(code=-1, result="no validate test data table"), 400
    return jsonify(code=0, result="ok")



if __name__ == '__main__':
    # opts = args_option()
    # log.debug("Start app at port {}!".format(opts.port))
    config_log({'level': 'debug'})
    db.create_all()
    manager.run()
