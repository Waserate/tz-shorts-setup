local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
--
local exports = exports or {}
local makeup = makeup or {}
---
---@class makeup : ScriptComponent [UI(Display="makeup")]
---@field test boolean
---@field intensity double [UI(Range={0, 1}, Drag)]
---

makeup.__index = makeup

-- output
local FACE_ADJUST = "face_adjust"
local FACE_ID = "id"
local FACE_ADJUST_INTENSITY = "intensity"
local FACE_ADJUST_PREFAB_PATH = "path"
local RESET_PARAMS = "reset_makeup_root"

-- runtime
local EPSC = 0.001
local SEGMENT_ID = "segmentId"
local LOG_TAG = "AE_EFFECT_TAG makeup.lua"

local PredefinedMakeupEntityList = {
    "Brow",
    "Eyeshadow",
    "Eyeline",
    "Eyemazing",
    "Eyelash",
    "Pupil",
    "Stereo",
    "Blusher",
    "Lip",---blendmode multiply
    "Lip_BlendModeColor",
    "Lip_BlendModeScreen",
}

local PredefinedFace3dEntityList = {
    "Freckles",
    "Highlight",
}

local tagNameList = {
    "face_adjust_brow",
    "face_adjust_eyeshadow",
    "face_adjust_eyeline",
    "face_adjust_eyemazing",
    "face_adjust_eyelash",
    "face_adjust_pupil",
    "face_adjust_stereo",
    "face_adjust_blusher",
    "face_adjust_lip",
    "face_adjust_mask",
    "face_adjust_highlight",
}

function makeup.new(construct, ...)
    local self = setmetatable({}, makeup)
    self.entities = {}
    -- param
    self.maxFaceNum = 10
    self.maxDisplayNum = 5
    self.rootDir = ""
    self.prefabMaterialMap = {}

    self.faceAdjustMapsTable = {}  -- save the input adjust event
    self.makeupEvents = {}         -- parser faceAdjustMapsTable, to get which entity should use which material in which tracking id

    self.isUpdated = false

    -- for test
    self.test = false
    self.intensity = 0.8

    return self
end

function makeup:isStringInList(str, list)
    for i = 1, #list do
        if str == list[i] then
            return true
        end
    end
    return false
end

function makeup:onStart(comp, script)
    local scene = comp.entity.scene
    self.scriptProps = comp.properties
    local segmentId = self.scriptProps:get(SEGMENT_ID)
    if segmentId ~= nil then
        self.logTag = string.format('%s %s', LOG_TAG, segmentId)
    else
        self.logTag = LOG_TAG
    end

    self.rootDir = scene.assetMgr.rootDir

    script:clearAllEventType()
    script:addEventType(Amaz.AppEventType.SetEffectIntensity)

    local entities = scene.entities
    for i = 0, entities:size() - 1 do
        local entity = entities:get(i)

        if self:isStringInList(entity.name, PredefinedMakeupEntityList) then
            self.entities[entity.name] = entity
        end
    end

    self.face3d = {}
    self.makeup3dCameraEntity = comp.entity:searchEntity("Makeup3DCamera")
    if self.makeup3dCameraEntity then
        for i = 1, self.maxDisplayNum do
            local entity = self.makeup3dCameraEntity:searchEntity("Face3D" .. i - 1)
            self.face3d[i] = entity
        end
    end

    self.camera2d = comp.entity:searchEntity("Makeup2DCamera"):getComponent("Camera")
end

function makeup:onUpdate(comp, deltaTime)
    -- Amaz.LOGI(LOG_TAG, "onUpdate")
    -- get face info by size order
    self:updateFaceInfoBySize()

    --parser faceAdjustMapsTable to get its entity should valid on which tracking id and which material it should use
    self:parserAdjustEvent()

    local tempIntensity = {}
    for _, rootEntityName in pairs(PredefinedMakeupEntityList) do
        local rootEntity = self.entities[rootEntityName]

        if rootEntity then
            local transforms = rootEntity:getComponentsRecursive("Transform")
            if not self.test then
                -- set all entity invisible
                for j = 0, transforms:size() - 1 do
                    local transform = transforms:get(j)
                    if transform then
                        transform.entity.visible = false
                        -- Amaz.LOGI(LOG_TAG, 'invisible ' .. transform.entity.name)
                    end
                end
            end

            tempIntensity[rootEntityName] = {}
            for f_idx = 0, self.maxFaceNum - 1 do
                tempIntensity[rootEntityName][f_idx] = {materials = {}, intensity = 0}
                
                -- for test
                if self.test then
                    tempIntensity[rootEntityName][f_idx].intensity = self.intensity
                end
            end

            for ind = 1, self.maxDisplayNum do -- maxFaceNum
                local faceInfo = self.faceInfoBySize[ind]
                local tracking_id = faceInfo.id   -- tracking id
                local index = faceInfo.index  -- n-th of the face result
                if  self.makeupEvents[rootEntityName] ~= nil
                and self.makeupEvents[rootEntityName][tracking_id] ~= nil
                and self.makeupEvents[rootEntityName][tracking_id]['intensity'] > 0
                then
                    tempIntensity[rootEntityName][index] = self.makeupEvents[rootEntityName][tracking_id]

                    -- set all entity visible
                    for j = 0, transforms:size() - 1 do
                        local transform = transforms:get(j)
                        if transform then
                            transform.entity.visible = true
                            -- Amaz.LOGI(LOG_TAG, 'visible ' .. transform.entity.name)
                        end
                    end
                end
            end
        end
    end

    for _, rootEntityName in pairs(PredefinedMakeupEntityList) do
        local rootEntity = self.entities[rootEntityName]

        if rootEntity ~= nil then
            local makeup = rootEntity:getComponent("EffectFaceMakeup")
            local renderers = rootEntity:getComponentsRecursive("MeshRenderer")
            if makeup ~= nil and not renderers:empty() and rootEntity.visible then
                for j = 0, renderers:size() - 1 do
                    local renderer = renderers:get(j)
                    if renderer then
                        -- Amaz.LOGI(LOG_TAG, 'rootEntity: ' .. rootEntityName .. ', curEntity: ' .. renderer.entity.name .. ' visible: ' .. tostring(renderer.entity.visible))
                        local materials = Amaz.Vector()
                        local table = renderer.entity:getComponent("TableComponent")
                        if table then
                            local defaultMaterial = table.table:get('default')
                            if tempIntensity[rootEntityName] then
                                for f_idx = 0, self.maxFaceNum - 1 do
                                    local mat = nil
                                    local params = tempIntensity[rootEntityName][f_idx]
                                    if params then
                                        local mats = params["materials"]
                                        for name, material in pairs(mats) do
                                            if renderer.entity.name == name then
                                                mat = material
                                                break
                                            end
                                        end
                                    end
                                    if mat ~= nil then
                                        -- Amaz.LOGI(LOG_TAG, "apply prefab material " .. renderer.entity.name .. ', f_idx: ' .. f_idx)
                                        local mat_ = mat:instantiate()

                                        if makeup.type == Amaz.EffectFaceMakeupType.PUPIL
                                        or makeup.type == Amaz.EffectFaceMakeupType.FACEU_PUPIL then
                                            if renderer.entity.name == rootEntityName then
                                                -- Amaz.LOGI(LOG_TAG, "set input tex for pupil material, " .. renderer.entity.name .. ', f_idx: ' .. f_idx)
                                                mat_:setTex('inputImageTexture', self.camera2d.renderTexture)
                                            end
                                        end

                                        materials:pushBack(mat_)
                                    else
                                        -- Amaz.LOGI(LOG_TAG, "apply default material " .. renderer.entity.name .. ', f_idx: ' .. f_idx)
                                        materials:pushBack(defaultMaterial)
                                    end
                                end
                            else
                                Amaz.LOGE(LOG_TAG, 'tempIntensity[' .. rootEntityName .. '] null')
                                materials:pushBack(defaultMaterial)
                            end
                        else
                            Amaz.LOGE(LOG_TAG, "No table found! Entity: " .. renderer.entity.name)
                        end
                        renderer.sharedMaterials = materials
                    end
                end

                --need to init makeup comp to avoid it is not inited
                makeup:onInit()
                -- we have to update opacite after set sharedMaterials
                if tempIntensity[rootEntityName] then
                    for f_idx = 0, self.maxFaceNum - 1 do
                        local params = tempIntensity[rootEntityName][f_idx]
                        if params then
                            local intensity = params['intensity']
                            if intensity ~= nil then
                                -- Amaz.LOGI(LOG_TAG, "entity: " .. rootEntityName .. ", f_id: " .. f_idx .. " apply opacity intensity: " .. intensity)
                                makeup:setFaceUniform("opacity", f_idx, intensity)
                            else
                                makeup:setFaceUniform("opacity", f_idx, 0.0)
                            end
                        end
                    end
                end
            end
        end
    end

    -- update face3d
    for i = 1, self.maxDisplayNum do
        if self.face3d[i] then
            self.face3d[i].visible = false
            local renderer = self.face3d[i]:getComponent("MeshRenderer")

            local faceInfo = self.faceInfoBySize[i]
            local tracking_id = faceInfo.id
            local index = faceInfo.index
            local mesh = faceInfo.mesh
            -- Amaz.LOGI(LOG_TAG, 'i: ' .. i .. ', tracking_id: ' .. tracking_id .. ', index: ' .. index)

            if renderer then
                for _, rootEntityName in pairs(PredefinedFace3dEntityList) do
                    
                    -- for test
                    if self.test then
                        if self.makeupEvents[rootEntityName] == nil then
                            self.makeupEvents[rootEntityName] = {}
                        end
                        if self.makeupEvents[rootEntityName][tracking_id] == nil then
                            self.makeupEvents[rootEntityName][tracking_id] = {
                                intensity = self.intensity,
                                materials = {renderer.sharedMaterial},
                            }
                        end
                    end

                    if  self.makeupEvents[rootEntityName] ~= nil
                    and self.makeupEvents[rootEntityName][tracking_id] ~= nil
                    and self.makeupEvents[rootEntityName][tracking_id]['intensity'] > 0
                    and mesh ~= nil
                    then
                        self.face3d[i].visible = true
                        local makeup3dOpacity = self.makeupEvents[rootEntityName][tracking_id]['intensity']
                        local material = self.makeupEvents[rootEntityName][tracking_id]['materials'][1]
                        if rootEntityName == "Freckles" then
                            renderer.props:setFloat("u_enableMask", 1)
                            renderer.props:setFloat("uMaskOpacity", makeup3dOpacity)
                            renderer.props:setTexture("uMaskTexture", material:getTex("uMaskTexture"))
                            -- Amaz.LOGI(LOG_TAG, 'i: ' .. i .. ', enalbe Freckles, intensity: ' .. makeup3dOpacity)
                        elseif rootEntityName == "Highlight" then
                            renderer.props:setFloat("u_enableHighlight", 1)
                            renderer.props:setFloat("uHighlightOpacity", makeup3dOpacity)
                            renderer.props:setTexture("uHighlightMask", material:getTex("uHighlightMask"))
                            -- Amaz.LOGI(LOG_TAG, 'i: ' .. i .. ', enalbe Highlight, intensity: ' .. makeup3dOpacity)
                        else
                            Amaz.LOGE(LOG_TAG, 'i: ' .. i .. ', Unsupport face3d makeup: ' .. rootEntityName)
                        end

                        local faceMVP = mesh.data:get("mvp")
                        local faceModel = mesh.data:get("modelMatrix")
                        local facePos = mesh.data:get("vertexes")
                        local faceNormals = mesh.data:get("normals")
                        if facePos:size() >= 1200 then
                            renderer.mesh:setVertexArray(facePos)
                            renderer.mesh:setNormalArray(faceNormals)
                            renderer.props:setMatrix("uModel", faceModel)
                            renderer.props:setMatrix("uMVP", faceMVP)
                        end
                    else
                        if rootEntityName == "Freckles" then
                            renderer.props:setFloat("u_enableMask", 0)
                        elseif rootEntityName == "Highlight" then
                            renderer.props:setFloat("u_enableHighlight", 0)
                        end
                    end
                end
            end
        end
    end

    self.isUpdated = true
end

function makeup:onEvent(comp, event)
    if event.type == Amaz.AppEventType.SetEffectIntensity then
        self:handleIntensityEvent(comp, event)
    end
end

function makeup:handleIntensityEvent(comp, event)
    local key = event.args:get(0)
    -- Amaz.LOGI(LOG_TAG, "onEvent: key ="..key)
    if key == RESET_PARAMS then
        self.faceAdjustMapsTable = {}
        return
    end

    for _, tagName in pairs(tagNameList) do
        if string.sub(key, 1, string.len(tagName)) == tagName then
            self:eventDataToTable(key, event.args:get(1))
        end
    end
end

function makeup:eventDataToTable(key, data)
    if self.isUpdated then 
        self.faceAdjustMapsTable = {}
        self.isUpdated = false
    end 

    for j = 0, data:size() - 1 do
        if  data:get(j):has(FACE_ID)
        and data:get(j):has(FACE_ADJUST_INTENSITY)
        and data:get(j):has(FACE_ADJUST_PREFAB_PATH)
        then 
            local id = data:get(j):get(FACE_ID)
            local intensity = data:get(j):get(FACE_ADJUST_INTENSITY)
            local path = data:get(j):get(FACE_ADJUST_PREFAB_PATH)
            if self.faceAdjustMapsTable[key] == nil then 
                self.faceAdjustMapsTable[key] = {}
            end
            self.faceAdjustMapsTable[key][j] = {trackingId = id, intensity = intensity, path = path}
            -- Amaz.LOGI(LOG_TAG, "data to table key: "..key.." intensity: "..intensity.." id: "..id)
        else
            -- Amaz.LOGI(LOG_TAG, "data to table faild, key: "..key)
        end 
    end 
end 

function makeup:parserAdjustEvent()
    self.makeupEvents = {}

    --first， we parser the original adjust event, decompose those event which tracking id is -1 to the display tracking id.
    --we should discard intensity = 0
    local faceAdjustMapsTableTmp = {}
    for key, intensityVec in pairs(self.faceAdjustMapsTable) do
        faceAdjustMapsTableTmp[key] = {}
        local count = 0

        for i = 1, self.maxDisplayNum do -- maxFaceNum
            local faceInfo = self.faceInfoBySize[i]
            local intensity = 0
            local prefab_path = nil

            --this logic is nessarry, because we can encounter this case:
            --[0] : key = "a", trackingid = -1, intensity = 1.0, path = "xxx"
            --[1] : key = "a", trackingid = 3, intensity = 0.0, path = "xxx"
            --we want to exclude the invalid trackingid = 3 event to prevent it affects other key which trackingid = 3 and intensity ~= 0
            for j = 0, #intensityVec do
                local inputMap = intensityVec[j]
                if inputMap and inputMap["trackingId"] then 
                    if faceInfo.id == inputMap["trackingId"] then
                        intensity = inputMap['intensity']
                        prefab_path = inputMap['path']
                    elseif -1 == inputMap["trackingId"] then
                        intensity = inputMap['intensity']
                        prefab_path = inputMap['path']
                    end
                end
            end

            if intensity > 0 and prefab_path ~= nil and faceInfo.id ~= -1 then
                faceAdjustMapsTableTmp[key][count] = {trackingId = faceInfo.id, intensity = intensity, path = prefab_path}
                count = count + 1
            end
        end
    end

    for key, intensityVec in pairs(faceAdjustMapsTableTmp) do
        for _, inputMap in pairs(intensityVec) do
            if  inputMap
            and inputMap["trackingId"]
            and inputMap["intensity"]
            and inputMap["path"]
            then
                local tracingId = inputMap["trackingId"]
                local intensity = inputMap["intensity"]
                local prefab_path = inputMap["path"]

                -- load prefab, and analysis these entities it contains
                -- prefab with same path is same one, so only load the material at the first time
                 if self.prefabMaterialMap[prefab_path] == nil then
                    self.prefabMaterialMap[prefab_path] = {}

                    local prefab = Amaz.PrefabManager.loadPrefab(prefab_path, "makeup.prefab")
                    if prefab then
                        prefab:init()
                        local prefab_entities = prefab.entities

                        -- for each makeup root entity, we set the corresponding tracing id , materials and intensity
                        for i = 0, prefab_entities:size() - 1 do
                            local makeupRootEntity = prefab_entities:get(i)

                            if self:isStringInList(makeupRootEntity.name, PredefinedMakeupEntityList) then
                                local makeup = makeupRootEntity:getComponent("EffectFaceMakeup")
                                if makeup then
                                    local renderers = makeupRootEntity:getComponentsRecursive("MeshRenderer")
                                    if not renderers:empty() then
                                        if self.makeupEvents[makeupRootEntity.name] == nil then
                                            self.makeupEvents[makeupRootEntity.name] = {}
                                        end
                                        local materials = {}
                                        for j = 0, renderers:size() - 1 do
                                            local renderer = renderers:get(j)
                                            if renderer then
                                                -- Amaz.LOGI(LOG_TAG, 'Get material for ' .. renderer.entity.name)
                                                materials[renderer.entity.name] = renderer.sharedMaterial
                                            end
                                        end
                                        self.prefabMaterialMap[prefab_path][makeupRootEntity.name] = materials
                                        self.makeupEvents[makeupRootEntity.name][tracingId] = {
                                            intensity = intensity,
                                            materials = materials,
                                        }
                                    else
                                        Amaz.LOGE(LOG_TAG, "load prefab failded! renderer is null")
                                    end
                                else
                                    Amaz.LOGE(LOG_TAG, "load prefab failded! makeup is null! Entity: " .. makeupRootEntity.name)
                                end
                            elseif self:isStringInList(makeupRootEntity.name, PredefinedFace3dEntityList) then
                                local renderer = makeupRootEntity:getComponent("MeshRenderer")
                                if renderer then
                                    if self.makeupEvents[makeupRootEntity.name] == nil then
                                        self.makeupEvents[makeupRootEntity.name] = {}
                                    end
                                    self.prefabMaterialMap[prefab_path][makeupRootEntity.name] = {renderer.sharedMaterial}
                                    self.makeupEvents[makeupRootEntity.name][tracingId] = {
                                        intensity = intensity,
                                        materials = {renderer.sharedMaterial},
                                    }
                                end
                            end
                        end                        
                    end

                    --release prefab
                    prefab = nil
                    collectgarbage("collect")
                 else
                    for name, materials in pairs(self.prefabMaterialMap[prefab_path]) do
                        if self.makeupEvents[name] == nil then
                            self.makeupEvents[name] = {}
                        end
                        self.makeupEvents[name][tracingId] = {
                            intensity = intensity,
                            materials = materials,
                        }
                    end
                 end
            end
        end
    end
end

function makeup:updateFaceInfoBySize()
    self.faceInfoBySize = {}

    local result = Amaz.Algorithm.getAEAlgorithmResult()
    local faceCount = result:getFaceCount()
    local freidCount = result:getFreidInfoCount()
    local facefittingCount = result:getAlgorithmInfoCount('new-model-2d-makeuproot', 'facefitting_3d_0', 'facefitting_3d')
    
    -- Amaz.LOGI(LOG_TAG, "faceCount: " .. faceCount .. ", facefittingCount: " .. facefittingCount)
    for i = 0, self.maxFaceNum - 1 do
        local trackId = -1
        local meshInfo = nil
        local faceSize = 0
        if i < faceCount then
            local baseInfo = result:getFaceBaseInfo(i)
            local faceId = baseInfo.ID
            local faceRect = baseInfo.rect

            for j = 0, freidCount - 1 do
                local freidInfo = result:getFreidInfo(j)
                if faceId == freidInfo.faceid then
                    trackId = freidInfo.trackid
                end
            end

            -- get face3d mesh info
            for j = 0, facefittingCount - 1 do
                local faceMeshInfo = result:getAlgorithmInfo('new-model-2d-makeuproot', 'facefitting_3d_0', 'facefitting_3d', j) 
                if (not faceMeshInfo) then
                    Amaz.LOGE(LOG_TAG, 'Invalid faceMeshInfo'..j)
                end
                if faceId == faceMeshInfo.data:get("face_id") then
                    meshInfo = faceMeshInfo
                end
            end

            faceSize = faceRect.width * faceRect.height
        end

        table.insert(self.faceInfoBySize, {
            index = i,
            id = trackId,
            mesh = meshInfo,
            size = faceSize
        })
    end
    table.sort(
        self.faceInfoBySize,
        function(a, b)
            return a.size > b.size
        end
    )
end

exports.makeup = makeup
return exports
