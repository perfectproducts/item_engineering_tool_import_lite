import omni.ext
from omni.kit.widget.browser_bar import widget
#from omni.services.transport.client.https_async import consumer
import omni.ui as ui
from pathlib import Path
import carb.settings
import os 
import asyncio
import webbrowser
from enum import IntEnum
import omni.kit.window.content_browser as content
from omni.kit.window.filepicker import FilePickerDialog


from pxr import Usd, Sdf, Gf, UsdGeom
from synctwin.item.connector.item_engineering_connector import ItemEngineeringConnector


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

    def get_icon_path(cls):
        extension_path = omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)
        icon_path = Path(extension_path).joinpath("data").joinpath("icons")
        return icon_path

    def on_base_directory_selected(self, dialog, dirname: str):        
        self._base_path_model.set_value(dirname)        
        self.update_settings()
        dialog.hide()

    def show_base_directory_selection_dialog(self):
        heading = "Select Folder..."
        dialog = FilePickerDialog(
            heading,
            
            apply_button_label="Select Directory",
            click_apply_handler=lambda filename, dirname: self.on_base_directory_selected(dialog, dirname),
            item_filter_options=None,
        )
        dialog.set_current_directory(self._base_path_model.get_value_as_string())
        dialog.show()

    def update_settings(self):
        self._settings.set("base_path", self._base_path_model.get_value_as_string())
        self._settings.set("project_url", self._project_url_model.get_value_as_string())        

    def on_startup(self, ext_id):        
        # our usd context 
        self._usd_context = omni.usd.get_context()
        # store settings
        self._settings = carb.settings.get_settings()    
        # content browser widget
        self._content_browser = content.get_content_window()

        # default to home directory 
        default_base_path = Path.home().as_posix()        
        default_project_url = "https://item.engineering/DEde/tools/engineeringtool/1aa62b1fe013ec5f83f83c1471c5ec124"

        #-- get values 
        base_path=self.settings_value("base_path", default_base_path)        
        project_url=self.settings_value("project_url", default_project_url)
        self._base_path_model = ui.SimpleStringModel(base_path)
        self._project_url_model = ui.SimpleStringModel(project_url)
        self._open_created_model = ui.SimpleBoolModel(True)

        self._item_connector = ItemEngineeringConnector(
            base_path=base_path,
            project_url=project_url
            )     

        self._window = ui.Window("synctwin item connector", width=300, height=200)

        with self._window.frame:
            with ui.VStack():
                omni.ui.Image(self.get_icon_path().joinpath("item_logo.png").absolute().as_posix(), width=80, height=30)

                ui.Label("Project Url", height=30)    
                project_url_field = ui.StringField(
                    model=self._project_url_model,
                    height=30
                    )

                ui.Spacer(height=10)
                ui.Label("Base-Path", height=30)
                with ui.HStack(height=30):                          
                    base_path_field = ui.StringField(                        
                        model=self._base_path_model,
                        height=30
                        )
                    ui.Button(
                        "...",
                        width=25,
                        height=30,
                        tooltip="select directory...",
                        clicked_fn=lambda: self.show_base_directory_selection_dialog()
                    )

                button_height = 40
                with ui.HStack(height=button_height):
                    ui.Label("open created", width=50 )
                    ui.Spacer(width=5)
                    with ui.VStack(width=10, height=button_height):
                        ui.Spacer()
                        ui.CheckBox(width=10, model=self._open_created_model)
                        ui.Spacer()
                    ui.Button("create usd", height=button_height, clicked_fn=lambda: on_update_clicked())     
               
                ui.Button("go to content browser", clicked_fn=lambda: on_goto_content_clicked(), height=button_height)
                
                ui.Button("open engineering tool project", height=button_height, tooltip="open engineering tool in browser", clicked_fn=lambda: on_browser_clicked())    
                ui.Spacer()

                def on_update_clicked():
                    base_path = self._base_path_model.get_value_as_string()
                    self.update_settings()
                    self._item_connector.set_base_path(base_path)
                    result = self._item_connector.import_project(project_url_field.model.get_value_as_string())
                    # store settings
                    
                    if self._open_created_model.get_value_as_bool():
                        omni.usd.get_context().open_stage(result)

                def on_goto_content_clicked():
                    if self._content_browser is not None:
                        self._content_browser.refresh_current_directory()
                        self._content_browser.navigate_to(self._item_connector.stage_path())
                        
                def on_browser_clicked():
                    self.open_browser(self._item_connector.project_url())                    

    # cleanup on shutdown  
    def on_shutdown(self):        
        self._settings = None
        self._window = None

        print("shutdown")
        
    # opens a system browser with given url 
    def open_browser(self, url):        
        webbrowser.open(url)

