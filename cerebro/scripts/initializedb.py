import os
import sys
import transaction

from sqlalchemy import engine_from_config

from pyramid.config import Configurator

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from ..models import (
    DBSession,
    Base,
    )

from ..models.project import *
from ..models.user import *


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)
    config_uri = argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)
    config = Configurator(settings)
    config.scan("cerebro.models")
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    conn = engine.connect()
    conn.execute("""
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
""")
    conn.execute("""
CREATE EXTENSION IF NOT EXISTS plv8;

CREATE TYPE doc_rev AS (doc_id integer, doc_rev integer);

CREATE FUNCTION subtree_at_path (j json, path integer array)
    RETURNS json
    LANGUAGE plv8
    IMMUTABLE
AS
$$
    path = path.slice();

    while (path.length > 0) {
        j = j.c[path.shift()];
    }

    return j;
$$;

CREATE FUNCTION all_docs_and_revs_for_tree (j json)
    RETURNS SETOF doc_rev
    LANGUAGE plv8
    IMMUTABLE
AS
$$
    var q = [j];
    var acc = [];

    while (q.length > 0) {
        v = q.pop();
        acc.push({
            doc_id: v.d,
            doc_rev: v.r
        });
        v.c.forEach(function (k) {
            q.push(k);
        });
    }

    return acc;
$$;

CREATE FUNCTION get_path_for_doc (j json, doc_id integer)
    RETURNS integer array
    LANGUAGE plv8
    IMMUTABLE
AS
$$
    var q = [[j]];
    var path;

    while (q.length > 0) {
        path = q.pop();
        var tail = path[path.length - 1];

        if (tail.d == doc_id) {
            return path.map(function (v) {
                return v.d;
            });
        }

        tail.c.forEach(function (k) {
            q.push(path.concat(k));
        });
    }

    return null;
$$;
""")
    Base.metadata.create_all(engine)

    with transaction.manager:
        print("Sample data!")

        test_user = User(name="test", email="test@example.com", pwhash="...")
        DBSession.add(test_user)

        test_project = Project(name="test-project", title="Test Project", owner=test_user)
        DBSession.add(test_project)

        test_tree = TreeRevision(project=test_project, tree_rev=-1, tree={})
    DBSession.expunge_all()
