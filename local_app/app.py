import datetime
import os.path

from flask import Flask

from connection import connection_string_azure_psql
from connection import connection_string_local_psql
from connection import connection_string_azure_data_lake
from connection import data_lake_folder

import psycopg2
import json
from azure.storage.blob import BlobServiceClient

app = Flask(__name__)


# Retrieve all shared overlays/data on centralized Azure psql database
@app.route('/shared')
def get_shared():
    dbconn = psycopg2.connect(**connection_string_azure_psql)
    cursor = dbconn.cursor()
    cursor.execute("""SELECT * from public.overlays""")
    ety = cursor.fetchall()
    rows = cursor.rowcount
    dbconn.commit()
    cursor.close()
    dbconn.close()
    json_response = None

    overlays = []
    for t in ety:
        json_response = {"created": t[0], "creator": t[1], "data_description": t[2], "data_name": t[3],
                         "file_path": t[4], "lr_lat": str(t[5]), "lr_lng": str(t[6]), "overlay_id": t[7],
                         "resolution": t[8], "ul_lat": str(t[9]), "ul_lng": str(t[10]), "is_earth_daily": t[11]}

        overlays.append(json_response)

    return json.dumps(json_response)


# Retrieve all local overlays/data on local psql database
@app.route('/local')
def get_local():
    dbconn = psycopg2.connect(**connection_string_local_psql)
    cursor = dbconn.cursor()
    cursor.execute("""SELECT * from public.overlays""")
    ety = cursor.fetchall()
    rows = cursor.rowcount
    dbconn.commit()
    cursor.close()
    dbconn.close()
    json_response = None

    overlays = []
    for t in ety:
        json_response = {"created": datetime.datetime.isoformat(t[9]), "creator": t[10], "data_description": t[2],
                         "data_name": t[1], "file_path": t[8], "lr_lat": str(t[5]), "lr_lng": str(t[6]),
                         "overlay_id": t[0], "resolution": t[7], "ul_lat": str(t[3]), "ul_lng": str(t[4]),
                         "is_earth_daily": t[11]}
        print(json_response)
        overlays.append(json_response)

    return json.dumps(json_response)


# Share a locally stored dataset from an IOT sensor/drone
@app.route('/share/local/<selected_id>')
def share_resource(selected_id):
    dbconn = psycopg2.connect(**connection_string_local_psql)
    cursor = dbconn.cursor()
    cursor.execute("""SELECT * from public.overlays WHERE overlay_id = %s """, (selected_id,))
    sel_ety = cursor.fetchone()
    f_rows = cursor.rowcount

    dbconn.commit()
    cursor.close()
    dbconn.close()

    # If there is nothing found to add then return
    if f_rows < 1:
        return

    # Connect to Azure and find how many entries currently exist
    dbconn = psycopg2.connect(**connection_string_azure_psql)
    cursor = dbconn.cursor()
    cursor.execute("""SELECT overlay_id from public.overlays""")
    ety = cursor.fetchall()
    c_rows = cursor.rowcount
    c_rows = c_rows + 1

    # Get filename from current path and update with full data lake location
    output_path = os.path.basename(sel_ety[8])
    output_path = data_lake_folder + str(c_rows) + "_" + output_path

    # Upload shared file to data lake storage
    blob_service_client = BlobServiceClient.from_connection_string(connection_string_azure_data_lake)
    container_client = blob_service_client.get_container_client("test")
    with open(sel_ety[8], "rb") as data:
        blob_client = container_client.upload_blob(name=output_path, data=data)

    cursor.execute(
        """INSERT INTO public.overlays (created, creator, data_description, data_name, file_path, lr_lat, lr_lng, 
        overlay_id, resolution, ul_lat, ul_lng, is_earth_daily) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
         %s)""", (sel_ety[9], sel_ety[10], sel_ety[2], sel_ety[1], output_path, sel_ety[5], sel_ety[6], c_rows,
                  sel_ety[7], sel_ety[3], sel_ety[4]), sel_ety[11])

    dbconn.commit()
    cursor.close()
    dbconn.close()


if __name__ == '__main__':
    app.run()