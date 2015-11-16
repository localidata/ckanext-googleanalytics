from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime
from sqlalchemy.sql import select, text
from sqlalchemy import func

import ckan.model as model
from ckan.lib.base import *
import datetime

cached_tables = {}

def init_tables():
    metadata = MetaData()
    package_stats = Table('package_stats', metadata,
                          Column('package_id', String(60)),
                          Column('visits', Integer),
                          Column('visit_date', DateTime))
    resource_stats = Table('resource_stats', metadata,
                           Column('resource_id', String(60)),
                           Column('visits', Integer),
                           Column('visit_date', DateTime))
    metadata.create_all(model.meta.engine)

def get_table(name):
    if name not in cached_tables:
        meta = MetaData()
        meta.reflect(bind=model.meta.engine)
        table = meta.tables[name]
        cached_tables[name] = table
    return cached_tables[name]

def _update_visits(table_name, item_id, visit_date, visits):
    stats = get_table(table_name)
    id_col_name = "%s_id" % table_name[:-len("_stats")]
    id_col = getattr(stats.c, id_col_name)
    visit_date_col = getattr(stats.c, 'visit_date')
    s = select([func.count(id_col)]).where(
               id_col == item_id)\
                .where(visit_date_col == visit_date)
    connection = model.Session.connection()
    count = connection.execute(s).fetchone()
    if count and count[0]:
        connection.execute(stats.update()\
            .where(id_col == item_id)\
            .where(visit_date_col == visit_date)
            .values(visits=visits))
    else:
        values = {id_col_name: item_id,
                  'visits': visits,
                  'visit_date': visit_date}
        connection.execute(stats.insert()\
                           .values(**values))


def update_resource_visits(resource_id,  visit_date, visits):
    return _update_visits("resource_stats",
                          resource_id,
                          visit_date,
                          visits)


def update_package_visits(package_id, visit_date, visits):
    return _update_visits("package_stats",
                          package_id,
                          visit_date,
                          visits)


def get_package_visits_for_id(id):
    q = """
        select visit_date, visits from package_stats, package
        where package.id = package_id
        and package.id = :id and visit_date >= :date_filter
        union all
        select null, sum(visits) from package_stats, package
        where package.id = package_id
        and package.id = :id
    """
    result = model.Session.connection().execute(text(q), id=id, date_filter=datetime.datetime.now() - datetime.timedelta(30)).fetchall()

    if result == [(None, None)]:
        result = []
    return result

def get_resource_visits_for_package_id(id):
    q = """
      select visit_date, visits, resource.url from resource_stats, resource, package
      where resource_stats.resource_id = resource.id
      and package.id = package_id
      and package.id = :id and visit_date >= :date_filter
      union all
      select null, sum(visits), null from resource_stats, resource, package
      where resource_stats.resource_id = resource.id
      and package.id = package_id
      and package.id = :id
    """
    result = model.Session.connection().execute(text(q), id=id, date_filter=datetime.datetime.now() - datetime.timedelta(30)).fetchall()
    if result == [(None, None)]:
        result = []
    return result

def get_resource_visits_for_url(url):
    q = """
        SELECT visit_date, visits FROM resource_stats, resource
        WHERE resource_id = resource.id
        AND resource.url = :url and visit_date >= :date_filter
        UNION ALL
        SELECT null, sum(visits) from resource_stats, resource
        WHERE resource_id = resource.id
        AND resource.url = :url
    """
    count = model.Session.connection().execute(text(q), url=url, date_filter=datetime.datetime.now() - datetime.timedelta(30)).fetchall()
    if count == [(None, None)]:
        count = []
    return count

def get_resource_visits_for_id(id):
    q = """
        SELECT visit_date, visits FROM resource_stats, resource
        WHERE resource_id = resource.id
        AND resource.id = :id and visit_date >= :date_filter
        UNION ALL
        SELECT null, sum(visits) from resource_stats, resource
        WHERE resource_id = resource.id
        AND resource.id = :id
    """
    count = model.Session.connection().execute(text(q), id=id, date_filter=datetime.datetime.now() - datetime.timedelta(30)).fetchall()
    if count == [(None, None)]:
        count = []
    return count

def get_latest_update_date():
    q = """
        SELECT max(visit_date) from resource_stats
        """
    result = model.Session.connection().execute(text(q)).first()
    if result == [(None, None)]:
        result = []
    return result[0].date()

def get_top_packages(limit=20):
    items = []
    # caveat emptor: the query below will not filter out private
    # or deleted datasets (TODO)
    q = model.Session.query(model.Package)
    connection = model.Session.connection()
    package_stats = get_table('package_stats')
    s = select([package_stats.c.package_id,
                package_stats.c.visits,
                package_stats.c.visit_date])\
                .order_by(package_stats.c.visit_date.desc())
    res = connection.execute(s).fetchmany(limit)
    for package_id, visits, visit_date in res:
        package_dict = {}
        item = q.filter("package.id = '%s'" % package_id)
        if not item.count():
            continue
        package_dict['package'] = item.first()
        package_dict['recent'] = visits
        package_dict['ever'] = visit_date
        items.append(package_dict)
    return items


def get_top_resources(limit=20):
    items = []
    connection = model.Session.connection()
    resource_stats = get_table('resource_stats')
    s = select([resource_stats.c.resource_id,
                resource_stats.c.visits,
                resource_stats.c.visit_date])\
                .order_by(resource_stats.c.visit_date.desc())
    res = connection.execute(s).fetchmany(limit)
    for resource_id, visits, visit_date in res:
        resource_dict = {}
        item = model.Session.query(model.Resource)\
               .filter("resource.id = '%s'" % resource_id)
        if not item.count():
            continue
        resource_dict['resource'] = item.first()
        resource_dict['recent'] = visits
        resource_dict['ever'] = visit_date
        items.append(resource_dict)
    return items
