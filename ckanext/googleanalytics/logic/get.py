from ckan.plugins import toolkit
from ckanext.googleanalytics import model

from datetime import datetime

@toolkit.side_effect_free
def most_visited_packages(context, data_dict):

    start_date = data_dict.get('start_date', None)
    end_date = data_dict.get('end_date', None)

    if start_date:
        start_date = datetime.strptime(start_date, "%d-%m-%Y")
    if end_date:
        end_date = datetime.strptime(end_date, "%d-%m-%Y")
    return model.PackageStats.get_top(start_date=start_date, end_date=end_date)