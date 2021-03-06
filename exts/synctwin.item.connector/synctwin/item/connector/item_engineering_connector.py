from pxr import Usd, Sdf, UsdGeom, Gf, Tf
from enum import IntEnum
import omni.services.client as OmniServicesClient
import omni.kit
import omni.client as OmniClient
import omni.ui as ui
import tempfile
import carb
import asyncio
import json 
import webbrowser


class LevelOfDetail(IntEnum):
    LOW = 0,
    MEDIUM = 1,
    HIGH = 2 

class ItemEndpointInfo:
    _host = "https://item.engineering"
    _blob_host = "https://cdn.item24.com"
    _itemtool_url = "DEde/tools/engineeringtool"    
    _geometry_info_endpoint = "dqart/0:DEde/project_utilities/get_geometry_info"
    

class ItemEngineeringConnector:
    
    _projects_path = "c:/temp/item_engineering_tool"
    _parts_path = "c:/temp/item_engineering_tool/parts"
    _project_url = "https://item.engineering/DEde/tools/engineeringtool/1d05717eb87cec4287ed241312306c5f4"
    _endpoint_info = ItemEndpointInfo()

    def __init__(self, base_path, project_url, endpoint_info= ItemEndpointInfo()):
        self._base_path = base_path
        self._project_url = project_url
        self._endpoint_info = endpoint_info
        self._omni_client = OmniServicesClient.AsyncClient(endpoint_info._host) 
        self._blob_client = OmniServicesClient.AsyncClient(endpoint_info._blob_host) 

    def set_base_path(self, base_path):
        if base_path.endswith("/"):
            base_path = base_path[:-1]
        self._base_path = base_path 
         
        self._projects_path = f"{base_path}/projects"
        self._parts_path = f"{base_path}/parts"

    def parts_path(self):
        return self._parts_path

    def project_url(self): 
        return self._project_url    

    def _open_or_create_stage(self, path, clear_exist=True):
        layer = Sdf.Layer.FindOrOpen(path)
        if not layer:
            layer = Sdf.Layer.CreateNew(path)
        elif clear_exist:
            layer.Clear()
            
        if layer:
            return Usd.Stage.Open(layer)
        else:
            return None

    def refresh_parts(self):
        self._ov_parts = []
        result, entries = OmniClient.list(self._parts_path)
        for entry in entries:
            self._ov_parts.append(entry.relative_path)
        print (f"parts refreshed from {self._parts_path}, found: {len(self._ov_parts)}")


    async def download_blob(self, temp_dir, geo_model, usd_filename):
        if not geo_model.startswith(self._endpoint_info._blob_host):
            print(f"## no blob url {geo_model}" )
            return ""
        blob_url = f'{geo_model[len(self._endpoint_info._blob_host)+1:]}'
        print(f"    download {blob_url}")                    
        blob = await self._blob_client.get(blob_url)
                        
        temp_blob_path =f"{temp_dir.name}/blob.obj" 
        blobfile = open(temp_blob_path, "wb") 
        blobfile.write(blob)
        blobfile.close()
                        
        print(f"written to temp: {temp_blob_path}")
                        

        converter_manager = omni.kit.asset_converter.get_instance()
        context = omni.kit.asset_converter.AssetConverterContext()
        context.ignore_materials = False                        
        output_path = f"{self._parts_path}/{usd_filename}"
        
        print("convert...")
        print("target:" + output_path)
        def convert_progress_callback(progress, total):
            print(f"convert progress: {float(progress) / total}")
        def material_loader(descr):
            print(f"material loader {descr}" )
        task = converter_manager.create_converter_task(temp_blob_path, output_path, convert_progress_callback, context, material_loader)
        success =  await task.wait_until_finished()
        print(f"success: {success}")
        if success:
            self._ov_parts.append(usd_filename)
        else:            
            detailed_status_code = task.get_status()
            detailed_status_error_string = task.get_detailed_error()
            print(f"error converting: {detailed_status_code} {detailed_status_error_string}...")
        return output_path

    async def _create_lod_stage(self, project_id, lod):
        print(f"create lod stage {project_id} lod {lod}...")

        lod_stage_path = f"{self._projects_path}/{project_id}/lod{lod}.usd"      
        
        lod_stage = self._open_or_create_stage(lod_stage_path)
        lod_world = lod_stage.DefinePrim("/World", "Xform")                
        UsdGeom.SetStageUpAxis(lod_stage, UsdGeom.Tokens.z)                
        lod_stage.SetDefaultPrim(lod_world)
        #-----------------------------------------
        with_product_info = 1        
        with_conveyor_info = 1
        with_material_info = 1
        url = f'{self._endpoint_info._geometry_info_endpoint}/{project_id}/{lod}/{with_product_info}/{with_conveyor_info}/{with_material_info}'

        doc = await self._omni_client.get(url)
        
        p_p_obj = doc.get('p', {})
        p_obj = p_p_obj.get('objects', {})
        pidx = 0
        temp_dir = tempfile.TemporaryDirectory()
        known_host = 'https://cdn.item24.com/object-assets/geometries/'

        for part_id in p_obj.keys():            
            part_obj = p_obj[part_id]
            part_group_id = part_obj['g_id']
            if part_group_id is None:
                print("empty partgroup id, set to group") 
                part_group_id = "_"
            else:
                part_group_id = part_group_id.replace('-','_')
            if "name" in part_obj:
                part_product_name = part_obj['name'] 
            else:
                part_product_name = "unknown"
            part_article_number = part_obj.get('art', "")
            part_roller_conveyor = part_obj.get('roller_conveyor')
            part_length = part_obj.get('length')
            
            idx = 0 
            pidx = pidx + 1 
            part_g_obj = part_obj['g']
            #print(f'PART {part_id} {pidx}/{ len(p_obj)} (geos:{len(part_g_obj)}): {part_product_name}')
            
            for geo_obj in part_g_obj:
                idx = idx + 1 

                geo_model = geo_obj['m']
                geo_scale = geo_obj['s']
                geo_position = geo_obj['p']
                geo_rotation = geo_obj['r']
                #print(f'  geo {geo_model}')
                self.prim = None
                prim_path = f"/World/g_{part_group_id}/a_{part_article_number}_{pidx}/m_{idx}"
                if geo_model.endswith(".obj"):
                    geo_model_url = geo_model
                    if geo_model.startswith(known_host):
                        geo_model = geo_model[len(known_host):]

                    usd_filename = f"g_{Tf.MakeValidIdentifier(geo_model)}.usd"
                    if usd_filename not in self._ov_parts:
                        print(f"downloading part {geo_model_url}")
                        await self.download_blob(temp_dir, geo_model_url, usd_filename)
                    
                    model = lod_stage.DefinePrim(prim_path, "")
                    model.SetInstanceable(False) 
                    
                    model_part = lod_stage.DefinePrim(prim_path+"/part", "")
                    
                    
                    model_part.GetReferences().AddReference(f"../../parts/{usd_filename}")
                    
                    
                    UsdGeom.Xformable(model_part).ClearXformOpOrder ()
                    UsdGeom.Xformable(model_part).AddTranslateOp().Set(Gf.Vec3f(geo_position["x"], geo_position["y"], geo_position["z"]))
                    UsdGeom.Xformable(model_part).AddRotateXYZOp().Set(Gf.Vec3f(geo_rotation["x"], geo_rotation["y"], geo_rotation["z"]))    
                    UsdGeom.Xformable(model_part).AddScaleOp().Set(Gf.Vec3f(geo_scale["x"], geo_scale["y"], geo_scale["z"]))    
                    
                elif geo_model == "cube":                    
                    #print(prim_path)
                    cube = lod_stage.DefinePrim(prim_path, "Cube")
                    cube.GetAttribute("size").Set(2.0)
                    
                    UsdGeom.Xformable(cube).ClearXformOpOrder ()
                    UsdGeom.Xformable(cube).AddTranslateOp().Set(Gf.Vec3f(geo_position["x"], geo_position["y"], geo_position["z"]))
                    UsdGeom.Xformable(cube).AddRotateXYZOp().Set(Gf.Vec3f(geo_rotation["x"], geo_rotation["y"], geo_rotation["z"]))    
                    UsdGeom.Xformable(cube).AddScaleOp().Set(Gf.Vec3f(geo_scale["x"], geo_scale["y"], geo_scale["z"]))    

                elif geo_model == "cylinder":
                    cylinder = lod_stage.DefinePrim(prim_path, "Cylinder")
                    cylinder.GetAttribute("radius").Set(1.0)
                    cylinder.GetAttribute("axis").Set("Y")
                    cylinder.GetAttribute("height").Set(1.0)
                    
                    
                    UsdGeom.Xformable(cylinder).ClearXformOpOrder ()
                    UsdGeom.Xformable(cylinder).AddTranslateOp().Set(Gf.Vec3f(geo_position["x"], geo_position["y"], geo_position["z"]))
                    UsdGeom.Xformable(cylinder).AddRotateXYZOp().Set(Gf.Vec3f(geo_rotation["x"], geo_rotation["y"], geo_rotation["z"]))    
                    UsdGeom.Xformable(cylinder).AddScaleOp().Set(Gf.Vec3f(geo_scale["x"], geo_scale["y"], geo_scale["z"]))    
                else :
                    print(f"unknown geo type {geo_model}")
        
        lod_stage.Save()
        
        return f"{project_id}/lod{lod}.usd"

    async def _create_main_stage(self, project_id):
        
        
        stage = self._open_or_create_stage(self.stage_path())
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z) 
        if stage is None:
            print("error creating stage")
            return None
        world_prim = stage.DefinePrim("/World", "Xform")         
        stage.SetDefaultPrim(world_prim)
        item_prim = stage.DefinePrim(f"/World/item_{project_id}", "Xform")       
        UsdGeom.Xformable(item_prim).ClearXformOpOrder () 
        UsdGeom.Xformable(item_prim).AddScaleOp().Set(Gf.Vec3f(0.1,0.1,0.1))
        UsdGeom.Xformable(item_prim).AddRotateXOp().Set(90)
        vset = item_prim.GetVariantSets().AddVariantSet('LOD')
        # Create variant options.
        vset.AddVariant('Low')        
        vset.AddVariant('Medium')
        vset.AddVariant('High') 

        vset.SetVariantSelection('Low')
        with vset.GetVariantEditContext():       
            low_lod_path = await self._create_lod_stage(project_id, LevelOfDetail.LOW) 
            item_prim.GetReferences().AddReference(low_lod_path)
            
        vset.SetVariantSelection('Medium')
        with vset.GetVariantEditContext():       
            medium_lod_path = await self._create_lod_stage(project_id, LevelOfDetail.MEDIUM)     
            item_prim.GetReferences().AddReference(medium_lod_path)            
        vset.SetVariantSelection('High')
        with vset.GetVariantEditContext():            
            high_lod_path = await self._create_lod_stage(project_id, LevelOfDetail.HIGH)
            item_prim.GetReferences().AddReference(high_lod_path)            
        
        stage.Save()
        #print(stage.GetRootLayer().ExportToString())
        print(f"written.{self.stage_path()}")
        return self.stage_path()

    def project_url(self):
        return self._project_url

    def project_id(self):
        return self._project_url.split("/")[-1]
        
    def stage_path(self):
        return f"{self._projects_path}/{Tf.MakeValidIdentifier(self.project_id())}.usd"

    def import_project(self, project_url):
        self.refresh_parts()
        self._project_url = project_url
        print(f"== IMPORT {project_url}=================")
        print(f"projects: {self._projects_path}")
        print(f"parts: {self._parts_path}")
        print(f"project: {self.project_id()}")
        
        
        loop = asyncio.get_event_loop()
        task = loop.create_task(self._create_main_stage(self.project_id()))
        r = loop.run_until_complete(task)
        return r
        

    