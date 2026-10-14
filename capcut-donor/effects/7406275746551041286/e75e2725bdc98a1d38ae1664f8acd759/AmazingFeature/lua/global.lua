local exports = exports or {}
local global = global or {}
global.__index = global

------------------------------------------------------------------
-- Tool function
function printAmazing(...)
    local arg = { ... }
    local msg = "mjd amazinglua: "
    for k, v in pairs(arg) do
        msg = msg .. tostring(v) .. " "
    end
    -- Amaz.LOGS("mjd", msg)
end

function makeTableStr(arg)
    local msg = ""
    if type(arg) == "table" then
        for k, v in pairs(arg) do
            if type(v) == "table" then
                local tmp =  makeTableStr(v)
                msg = msg .. tostring(k) .. ":{" .. tmp .. "},"
            else
                msg = msg .. tostring(k) .. "=" .. tostring(v) .. ","
            end
        end
    end
    return msg
end

function printAmazingTable(arg)
    if type(arg) == "table" then
        local msg = makeTableStr(arg)
        printAmazing(msg) 
    else
        printAmazing(arg)
    end
end

function table_leng(t)
    local leng=0
    for k, v in pairs(t) do
      leng=leng+1
    end
    return leng
end

------------------------------------------------------------------

local GRAPH_NAME = "2022-09-28_15-39-51_inner_tag__1__billliaom"
-- local ganTextureUniform = "ganTexture"
-- local inferenceNodeName = "Inference"
-- local resNodeName = "StyleTransferPostProcess"
-- local tfmNodeName = "FaceAlign_jybeauty"

local FACE_ID = "id"
local INTENSITY_TAG = "intensity"
local EPSC = 0.001
local Item_All = "face_adjust_all"
local Item_Yunfu = "face_adjust_yunfu"
local Item_Fuling = "face_adjust_fuling"
local Item_Lunkuopinghua = "face_adjust_lunkuopinghua"
local RESET_PARAMS = "reset_params"


function global.new(construct, ...)
    local self = setmetatable({}, global)
    self.comps = {}
    self.compsdirty = true

    self.maxFaceNum = 10
    self.maxDisplayNum = 5
    self.faceAdjustMaps = {}
    self.faceInfoBySize = {}
    self.intensityKeys = {
        Item_All,
        Item_Yunfu,
        Item_Fuling,
        Item_Lunkuopinghua
    }
    return self
end


function global:onStart(sys)

    printAmazing("entering")
    self.sys = sys
    self.state = -1

    self.camera_entity = {e = self.sys.scene:findEntityBy("Camera_entity")}
    self.camera_entity.cam = self.camera_entity.e:getComponent("Camera")
    self.camera_entity.trans = self.camera_entity.e:getComponent("Transform")

    -- get face_gan
    self.face_gan = {e = self.sys.scene:findEntityBy("face_gan")}
    self.face_gan.mr = self.face_gan.e:getComponent("MeshRenderer")

    self.fg_list = {self.face_gan}

    for i = 1, self.maxFaceNum - 1 do
        -- get target
        local ct = {e = self.sys.scene:cloneEntityFrom(self.face_gan.e)}
        ct.e.name = string.format("%s_cloned[%d]", self.face_gan.e.name, i)
        ct.mr = ct.e:getComponent("MeshRenderer")
        ct.trans = ct.e:getComponent("Transform")
        -- set corrent parent
        ct.trans.parent = self.camera_entity.trans
        self.camera_entity.trans.children:pushBack(ct.trans)
        -- set mesh and material
        ct.mr.mesh = self.face_gan.mr.mesh
        ct.mr.sharedMaterials = self.face_gan.mr.sharedMaterials
        -- add to list
        self.fg_list[#self.fg_list + 1] = ct
    end

    for i = 1, #self.fg_list do
        self.fg_list[i].e.visible = false
        self.fg_list[i].mr.enabled = false
    end

end

function global:onUpdate(sys, deltaTime)
    self.graph_name = GRAPH_NAME
    printAmazing("updateing")
    self:freid__gan()
end

-- function global:wf__gan()
--     -- disable them all
--     for i = 1, #self.fg_list do
--         self.fg_list[i].e.visible = false
--         self.fg_list[i].mr.enabled = false
--     end

--     local result = Amaz.Algorithm.getAEAlgorithmResult()
--     if (result == nil) then
--         return false
--     end

--     local face_count = result:getFaceCount()
--     if face_count == nil or face_count < 1 then
--         return false
--     end

--     for i = 0, face_count - 1 do
--         local cgan_tex = result:getOutputTexture(self.graph_name, "script_0",
--                                                  i * 2)
--         local cflow_tex = result:getOutputTexture(self.graph_name, "script_0",
--                                                   i * 2 + 1)
--         local tfm_info = result:getNHImageTfmInfo(self.graph_name, "FaceAlign_jybeauty",
--                                                   i)
--         if (cgan_tex == nil or cgan_tex.texture == nil or cflow_tex == nil
--             or cflow_tex.texture == nil or tfm_info == nil or tfm_info.mvp == nil) then
--             printAmazing("dame 1")
--             printAmazing("self.graph_anme", self.graph_name)
--             return false
--         end

--         self.fg_list[i + 1].mr.material:setTex("u_gan", cgan_tex.texture)
--         self.fg_list[i + 1].mr.material:setTex("u_flow", cflow_tex.texture)
--         self.fg_list[i + 1].mr.material:setMat4("u_mvpMat", tfm_info.mvp)

--         local mvpMat_rev = Amaz.Matrix4x4f()
--         tfm_info.mvp:copyMatrix(mvpMat_rev)
--         mvpMat_rev:invert_Full()
--         self.fg_list[i + 1].mr.material:setMat4("u_mvpMat_rev", mvpMat_rev)

--         self.fg_list[i + 1].e.visible = true
--         self.fg_list[i + 1].mr.enabled = true

--         printAmazing("this is good")
--     end
-- end

function global:freid__gan()
    -- disable them all
    for i = 1, #self.fg_list do
        self.fg_list[i].e.visible = false
        self.fg_list[i].mr.enabled = false
    end

    -- get face info by size order
    self:updateFaceInfoBySize()

    -- draw every face submesh
    local result = Amaz.Algorithm.getAEAlgorithmResult()
    if (result == nil) then
        return false
    end
    
    for i = 1, self.maxFaceNum do
        local faceInfo = self.faceInfoBySize[i]
        local id = faceInfo.id
        local index = faceInfo.index

        local intensityAll = 0
        local intensityYunfu = 0
        local intensityFuling = 0
        local intensityLunkuopinghua = 0

        -- check trackid, if id ~= -1, use event value
        if id ~= -1 and i <= self.maxDisplayNum then
            intensityAll = self:getValue(id, Item_All, 0)
            intensityYunfu = self:getValue(id, Item_Yunfu, 0)
            intensityFuling = self:getValue(id, Item_Fuling, 0)
            intensityLunkuopinghua = self:getValue(id, Item_Lunkuopinghua, 0)
        end

        -- check faceMax count, then reset intensity 0
        if index > result:getFaceCount()-1 then
            intensityAll = 0
            intensityYunfu = 0
            intensityFuling = 0
            intensityLunkuopinghua = 0
        end

        if math.abs(intensityAll) > EPSC then
            intensityYunfu = intensityAll
            intensityFuling = intensityAll
            intensityLunkuopinghua = intensityAll
        end

        local scriptInfo = result:getAlgorithmInfo(self.graph_name, "script_0", "", 0)
        local valid = false
        if scriptInfo ~= nil and scriptInfo.outputMap ~= nil then
            local outputMap =  scriptInfo.outputMap
            local value = outputMap:get("gan" .. tostring(index))
            valid = value == 1
        end

        if (math.abs(intensityYunfu) > EPSC or 
            math.abs(intensityFuling) > EPSC or 
            math.abs(intensityLunkuopinghua) > EPSC) and valid
        then
            local cgan_tex = result:getAlgorithmInfoByName(self.graph_name, "script_0", index , 1)
            local tfm_info = result:getNHImageTfmInfo(self.graph_name, "FaceAlign_jybeauty", index)
            if (cgan_tex == nil or cgan_tex.texture == nil or tfm_info == nil or tfm_info.mvp == nil) then
                printAmazing("error index=", index, " freid=", id)
                return false
            end

            self.fg_list[index + 1].mr.material:setTex("u_gan", cgan_tex.texture)
            self.fg_list[index + 1].mr.material:setMat4("u_mvpMat", tfm_info.mvp)

            local mvpMat_rev = Amaz.Matrix4x4f()
            tfm_info.mvp:copyMatrix(mvpMat_rev)
            mvpMat_rev:invert_Full()
            self.fg_list[index + 1].mr.material:setMat4("u_mvpMat_rev", mvpMat_rev)
            -- Amaz.Algorithm.setAlgorithmParamFloat(self.graph_name, "script_0", Item_Yunfu, intensityYunfu)
            -- Amaz.Algorithm.setAlgorithmParamFloat(self.graph_name, "script_0", Item_Fuling, intensityFuling)
            -- Amaz.Algorithm.setAlgorithmParamFloat(self.graph_name, "script_0", Item_Lunkuopinghua, intensityLunkuopinghua)
            self.fg_list[index + 1].mr.material:setFloat("u_h", intensityLunkuopinghua)
            printAmazing("yunfu=", intensityYunfu, "fuling=", intensityFuling, "lunkuopinghua=", intensityLunkuopinghua)

            self.fg_list[index + 1].e.visible = true
            self.fg_list[index + 1].mr.enabled = true

            printAmazing("this is good, index=", index, " freid=", id)            
        end
    end
end

-- function global:df__past_update()
--     for i = 0, maxFace - 1 do
--         local nodeInfo = result:getOutputTexture(GRAPH_NAME, "script_0",
--                                                  i * 2 + 1)
--         -- local nodeInfo = result:getNHImageInfo(GRAPH_NAME, resNodeName, i)
--         local tfmInfo = result:getNHImageTfmInfo(GRAPH_NAME, tfmNodeName, i)
--         if nodeInfo then
--             local meshRender = self.MeshRenders[i]
--             local material = meshRender.material
--             material:setMat4("mvpMat", tfmInfo.mvp)
--             -- use GPU texture directly in rendering
--             if nodeInfo.texture ~= nil then
--                 material:setTex(ganTextureUniform, nodeInfo.texture)
--             end
--             -- material:getTex(ganTextureUniform):storage(nodeInfo.image)
--             meshRender.enabled = true
--         end
--     end
-- end

function global:onEvent(sys, event)
    if event.type == Amaz.AppEventType.SetEffectIntensity then
        self:handleIntensityEvent(sys, event)
    end
end

function global:hitKey(key)
    for i = 1, #self.intensityKeys do
        if key == self.intensityKeys[i] then
            return true
        end
    end
    return false
end

function global:handleIntensityEvent(sys, event)
    local key = event.args:get(0)
    printAmazing("event key=", key)

    if key == RESET_PARAMS then
        self.faceAdjustMaps = {}
    elseif self:hitKey(key) then
        self.faceAdjustMaps[key] = event.args:get(1)

        local strOutput = key .. ";"
        local vec = self.faceAdjustMaps[key]
        local inputSize = vec:size()
        for i = 0, inputSize-1 do
            if i > 0 then
                strOutput = strOutput .. ";"
            end
            local inputMap = vec:get(i)
            local keys = inputMap:getVectorKeys()
            for j = 0, keys:size()-1 do
                if j > 0 then
                    strOutput = strOutput .. ","
        end
                strOutput = strOutput .. keys:get(j) .. "=" .. inputMap:get(keys:get(j))
            end
        end
        printAmazing(strOutput)
    end
end

function global:getValue(id, key, default)
    local vec = self.faceAdjustMaps[key]
    if vec == nil then
        return default
    end
    local intensity = default
    local inputSize = vec:size()
    local hit = false
    local val = default
    for i = 0, inputSize - 1 do
        local inputMap = vec:get(i)
        if id == inputMap:get(FACE_ID) and inputMap:has(INTENSITY_TAG) then
            intensity = inputMap:get(INTENSITY_TAG)
            hit = true
        elseif -1 == inputMap:get(FACE_ID) and inputMap:has(INTENSITY_TAG) then
            val = inputMap:get(INTENSITY_TAG)
        end
    end

    if hit == false then
        intensity = val
    end

    return intensity
end

function global:updateFaceInfoBySize()
    self.faceInfoBySize = {}

    local result = Amaz.Algorithm.getAEAlgorithmResult()
    local faceCount = result:getFaceCount()
    local freidCount = result:getFreidInfoCount()
    for i = 0, self.maxFaceNum - 1 do
        local trackId = -1
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
            faceSize = faceRect.width * faceRect.height
        end
        table.insert(self.faceInfoBySize, {
            index = i,
            id = trackId,
            size = faceSize
        })
    end

    table.sort(self.faceInfoBySize, function(a, b)
        return a.size > b.size
    end)

    -- printAmazing("faceInfoSize=", makeTableStr(self.faceInfoBySize))
end

exports.global = global
return exports
