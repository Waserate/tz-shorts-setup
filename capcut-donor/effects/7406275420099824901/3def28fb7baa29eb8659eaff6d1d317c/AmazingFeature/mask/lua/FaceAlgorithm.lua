local exports = exports or {}
local FaceAlgorithm = FaceAlgorithm or {}
FaceAlgorithm.__index = FaceAlgorithm

local maskTextureUniform = "maskTexture"
local maxFaceNum = 5
local state = 3

function string.starts(String,Start)
   return string.sub(String,1,string.len(Start))==Start
end

function string.ends(String,End)
   return End=='' or string.sub(String,-string.len(End))==End
end

function print(...)
    local arg = { ... }
    local msg = "effect_lua:"
    for k, v in pairs(arg) do
        msg = msg .. tostring(v) .. " "
    end
    Amaz.LOGI("FaceAlgorithm", msg)
end

function FaceAlgorithm.new(construct, ...)
    local self = setmetatable({}, FaceAlgorithm)
    self.comps = {}
    self.compsdirty = true
    self.maxFaceNum = 10
    self.maxDisplayNum = 5
    return self
end

function FaceAlgorithm:constructor()
    print('running: FaceAlgorithm:constructor')
end


function FaceAlgorithm:onComponentAdded(sys, comp)
    print('running: FaceAlgorithm:onComponentAdded')
    if comp:isInstanceOf("MeshRenderer") and string.starts(comp.entity.name, "face_") then
        self.comps[comp.entity.name] = comp
    end
end

function FaceAlgorithm:onComponentRemoved(sys, comp)
    print('running: FaceAlgorithm:onComponentRemoved')
    if comp:isInstanceOf("MeshRenderer") and string.starts(comp.entity.name, "face_") then
        self.comps[comp.entity.name] = nil
    end
end


function FaceAlgorithm:onStart(sys)
    print('running: FaceAlgorithm:onStart')
    sys:addEventType(Amaz.EventType.TOUCH)
end

--local dw = Amaz.Algorithm.getDisplayWidth()
--local dh = Amaz.Algorithm.getDisplayHeight()

function FaceAlgorithm:onUpdate(sys, deltaTime)
    
    self:updateFaceInfoBySize()
    local meshRenderer = self.comps["face_0"]
    if meshRenderer == nil then
        Amaz.LOGE("FaceAlgorithm", " FaceAlgorithm:onUpdate mask meshRenderer is nil")
        return;
    end

    local material = meshRenderer.material
    if #self.faceInfoBySize < 1 then 
        material:setInt("faceCount", 0)
        Amaz.LOGE("FaceAlgorithm", " FaceAlgorithm:onUpdate faceCount < 1")
        return
    end

    local faceIdx = 0
    meshRenderer.mesh.clearAfterUpload = false
    for i = 1, #self.faceInfoBySize do
        if faceIdx < self.maxDisplayNum then
            local faceMask = self.faceInfoBySize[i].faceMask
            if faceMask then
                self:updateFace(faceMask, material, faceIdx)
                faceIdx = faceIdx + 1
            end
        end
    end
    material:setInt("faceCount", faceIdx)
end

function FaceAlgorithm:updateFace(faceMask, material, i)

    local warp_mat = faceMask.warp_mat
    local W = faceMask.face_mask_size
    local H = faceMask.face_mask_size

    local modelMatrix = Amaz.Matrix4x4f()
    modelMatrix:SetRow(0, Amaz.Vector4f(warp_mat:get(0) / W, warp_mat:get(1) / W, 0.0, warp_mat:get(2) / W))
    modelMatrix:SetRow(1, Amaz.Vector4f(warp_mat:get(3) / H, warp_mat:get(4) / H, 0.0, warp_mat:get(5) / H))
    modelMatrix:SetRow(2, Amaz.Vector4f(0.0, 0.0, 1.0, 0.0))
    modelMatrix:SetRow(3, Amaz.Vector4f(0.0, 0.0, 0.0, 1.0))

    material:setMat4("u_MVP_"..i, modelMatrix)

    local baseColor = Amaz.Vector4f(1.0, 1.0, 1.0, 1.0)
    if i == 1 then
        baseColor = Amaz.Vector4f(1.0, 0.0, 0.0, 1.0)
    elseif i == 2 then
        baseColor = Amaz.Vector4f(0.0, 1.0, 0.0, 1.0)
    elseif i == 3 then
        baseColor = Amaz.Vector4f(0.0, 0.0, 1.0, 1.0)
    elseif i == 4 then
        baseColor = Amaz.Vector4f(1.0, 1.0, 0.0, 1.0)
    end 
    material:setVec4("u_baseColor", baseColor)

    local tex = material:getTex(maskTextureUniform..i)
    if tex == nil then
        tex = Amaz.Texture2D()
        tex.filterMin = Amaz.FilterMode.LINEAR
        tex.filterMag = Amaz.FilterMode.LINEAR
        material:setTex(maskTextureUniform..i, tex)
    end

    -- load mask texture
    tex:storage(faceMask.image)
end

function FaceAlgorithm:onEvent(sys, event)
    print("onEvent event type: " .. event.type)
    if event.type == Amaz.EventType.TOUCH then
        local touch_phase = event.args:get(0)
        print("onEvent event touch phase type: " .. touch_phase.type)
        if touch_phase.type == Amaz.TouchType.TOUCH_ENDED then
            state = state + 1
            if state >= 4 then
                state = 1
            end
            print("onEvent click switch state " .. state)
        end
    end
end

function FaceAlgorithm:updateFaceInfoBySize()
    self.faceInfoBySize = {}

    local result = Amaz.Algorithm.getAEAlgorithmResult()
    local faceCount = result:getFaceCount()
    local freidCount = result:getFreidInfoCount()
    -- Amaz.LOGS(self.logTag, "updateFaceInfoBySize faceCount " .. faceCount .. " freidCount " .. freidCount)
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
            faceSize = faceRect.width * faceRect.height
        end
        table.insert(self.faceInfoBySize, {
            index = i,
            id = trackId,
            size = faceSize,
            faceMask = result:getFaceFaceMask(i)
        })
        
    end
    table.sort(self.faceInfoBySize, function(a, b)
        return a.size > b.size or (a.size == b.size and a.index < b.index)
    end)
end

exports.FaceAlgorithm = FaceAlgorithm
return exports
