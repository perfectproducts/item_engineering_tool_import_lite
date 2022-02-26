import omni.ext
#from omni.services.transport.client.https_async import consumer
import omni.ui as ui
from pathlib import Path
import carb.settings
import os 
import asyncio
import webbrowser
from enum import IntEnum
import omni.kit.window.content_browser as content



from pxr import Usd, Sdf, Gf, UsdGeom
from synctwin.item.connector.item_engineering_connector import ItemEngineeringConnector
ICON_PATH = Path(__file__).parent.parent.parent.parent.joinpath("data")

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.

class ItemConnectorExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    def settings_value(self, key, default_value="")->str : 
        result=self._settings.get(key)
        if result == None:
            result = default_value
        return result 
    
    def on_startup(self, ext_id):
        
        self._usd_context = omni.usd.get_context()

        self._settings = carb.settings.get_settings()    
        self._content_browser = content.get_content_window()
        default_base_path = "omniverse://b2e75b34-0278-49e2-b28d-08af7323a8bc.cne.ngc.nvidia.com"
        default_projects_path = "Library/Racks/item"
        default_parts_path = "Library/Racks/item/parts"
        default_project_url = "https://item.engineering/DEde/tools/engineeringtool/1d05717eb87cec4287ed241312306c5f4"

        #-- get values 
        base_path= self.settings_value("base_path", default_base_path)
        projects_path= self.settings_value("projects_path", default_projects_path)        
        parts_path= self.settings_value("parts_catalog_url", default_parts_path)
        project_url=self.settings_value("project_url", default_project_url)

        
        self._item_connector = ItemEngineeringConnector(
            projects_path=f"{base_path}/{projects_path}",
            parts_path=f"{base_path}/{parts_path}",
            project_url=project_url
            )     

        print("[synctwin.item.connector] synctwin item startup")

        self._window = ui.Window("synctwin item connector", width=300, height=200)

        with self._window.frame:
            with ui.VStack():
                
                with ui.HStack():                    
                    
                    omni.ui.Image(f'{ICON_PATH}/item_logo.png', width=80)
                    
                ui.Label("Base-Path")    
                base_path_field = ui.StringField(height=30)
                base_path_field.model.set_value(base_path)

                ui.Label("Parts-Path")    
                parts_path_field = ui.StringField(height=30)
                parts_path_field.model.set_value(parts_path)

                ui.Label("Projects-Path")    
                catalog_path_field = ui.StringField(height=30)
                catalog_path_field.model.set_value(projects_path)

                ui.Label("Project Url")    
                project_url_field = ui.StringField(height=30)
                project_url_field.model.set_value(project_url)
                ui.Label("open created")
                self._open_check = ui.CheckBox()
                def on_update_clicked():
                    result = self._item_connector.import_project(project_url_field.model.get_value_as_string())
                    # store settings
                    self._settings.set("base_path", base_path_field.model.get_value_as_string())
                    self._settings.set("projects_path", catalog_path_field.model.get_value_as_string())
                    self._settings.set("parts_catalog_url", parts_path_field.model.get_value_as_string())
                    self._settings.set("project_url", project_url_field.model.get_value_as_string())
                    if self._open_check.model.get_value_as_bool():
                        omni.usd.get_context().open_stage(result) 

                def on_goto_content_clicked():
                    if self._content_browser is not None:
                        self._content_browser.navigate_to(self._item_connector.stage_path())

                ui.Button("create usd", height=40, clicked_fn=lambda: on_update_clicked())
                ui.Button("go to content browser", clicked_fn=lambda: on_goto_content_clicked())
                def on_browser_clicked():
                    self.open_browser(self._item_connector.project_url())                    
                ui.Button("open browser", height=40, tooltip="open engineering tool in browser", clicked_fn=lambda: on_browser_clicked())    

                
    
    def on_shutdown(self):        
        self._window = None 
        self._settings = None 
        self._item_connector = None
        self._content_browser = None


    def open_browser(self, url):        
        webbrowser.open(url)

