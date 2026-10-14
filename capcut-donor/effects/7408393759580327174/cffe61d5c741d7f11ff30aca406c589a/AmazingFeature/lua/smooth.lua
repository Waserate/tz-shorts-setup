local exports = exports or {}
local smooth = smooth or {}
smooth.__index = smooth

-- output
local FACE_INFO = "face_info"
local FACE_COUNT_EXCEED_MAX = "face_count_exceed_max"
local FACE_ADJUST = "face_adjust"
local FACE_ID = "id"
local FACE_INDEX = "index"
local FACE_BBOX = "bbox"
local FACE_DIRECT = "direct"
local FACE_ADJUST_INTENSITY = "intensity"

-- runtime
local MIN = math.min
local MAX = math.max
local MOD = math.modf
local EPSC = 0.001
local SEGMENT_ID = "segmentId"
local LOG_TAG = "AE_EFFECT_TAG smooth.lua"

function smooth.new(construct, ...)
    local self = setmetatable({}, smooth)

    -- param
    self.maxFaceNum = 10
    self.maxDisplayNum = 5
    self.faceAdjustMaps = {}

    -- init
    local defaultMap = Amaz.Map()
    defaultMap:set(FACE_ID, -1)
    defaultMap:set(FACE_ADJUST_INTENSITY, 0)
    self.faceAdjustMaps[-1] = defaultMap

    return self
end

function smooth:onStart(comp, script)
    local scene = comp.entity.scene
    self.scriptProps = comp.properties
    local segmentId = self.scriptProps:get(SEGMENT_ID)
    if segmentId ~= nil then
        self.logTag = string.format('%s %s', LOG_TAG, segmentId)
    else
        self.logTag = LOG_TAG
    end

    self.smoothGroup = scene:findEntityBy("smooth")
    local makeupEntity = scene:findEntityBy("mask")
    self.makeupComp = makeupEntity:getComponent("EffectFaceMakeupFaceU")
    self.makeupRenderer = makeupEntity:getComponent("MeshRenderer")
    local hsvEntity = scene:findEntityBy("hsv")
    self.hsvRenderer = hsvEntity:getComponent("MeshRenderer")
    local blur1Entity = scene:findEntityBy("blur1")
    self.blur1Renderer = blur1Entity:getComponent("MeshRenderer")
    local blur2Entity = scene:findEntityBy("blur2")
    self.blur2Renderer = blur2Entity:getComponent("MeshRenderer")
    local blur3Entity = scene:findEntityBy("blur3")
    self.blur3Renderer = blur3Entity:getComponent("MeshRenderer")
    local blur4Entity = scene:findEntityBy("blur4")
    self.blur4Renderer = blur4Entity:getComponent("MeshRenderer")
end

function smooth:onUpdate(comp, deltaTime)
    -- get face info by size order
    self:updateFaceInfoBySize()

    -- update render state
    self.inputWidth = Amaz.BuiltinObject:getInputTextureWidth()
    self.inputHeight = Amaz.BuiltinObject:getInputTextureHeight()
    self.widthOffset = 1 / MOD(self.inputWidth * 0.45)
    self.heightOffset = 1 / MOD(self.inputHeight * 0.45)
    self.blur1Renderer.material:setFloat("texBlurWidthOffset", self.widthOffset)
    self.blur2Renderer.material:setFloat("texBlurHeightOffset", self.heightOffset)
    self.blur3Renderer.material:setFloat("widthOffset", self.widthOffset)
    self.blur3Renderer.material:setFloat("heightOffset", self.heightOffset)
    self.blur4Renderer.material:setFloat("widthOffset", self.widthOffset)
    self.blur4Renderer.material:setFloat("heightOffset", self.heightOffset)

    -- update face with valid track id
    local isVisible = false
    for i = 1, self.maxFaceNum do
        local faceInfo = self.faceInfoBySize[i]
        local id = faceInfo.id
        local intensity = 0
        if id ~= -1 and i <= self.maxDisplayNum then
            local adjustMap = self.faceAdjustMaps[id]
            if adjustMap == nil then
                adjustMap = self.faceAdjustMaps[-1]
            end
            intensity = adjustMap:get(FACE_ADJUST_INTENSITY)
        end
        if intensity > EPSC then
            isVisible = true
        end
        self.makeupComp:setFaceUniform("opacity", faceInfo.index, intensity)
    end
    local intensity = self.faceAdjustMaps[-1]:get(FACE_ADJUST_INTENSITY)
    if intensity > EPSC then
        isVisible = true
    end
    self.hsvRenderer.material:setFloat("skinIntensity", intensity)
    self.smoothGroup.visible = isVisible
    -- Amaz.Algorithm.setAlgorithmEnable(comp.entity.scene.name, "skin_seg_0", isVisible)
end

function smooth:onLateUpdate(comp, deltaTime)
    -- update face algo params
    local result = Amaz.Algorithm.getAEAlgorithmResult()
    local faceAlgoParams = Amaz.Vector()
    local faceCountExceedMax = false
    for i = 1, self.maxDisplayNum do
        local faceInfo = self.faceInfoBySize[i]
        local id = faceInfo.id
        local index = faceInfo.index
        if id ~= -1 then
            local baseInfo = result:getFaceBaseInfo(index)
            local algoMap = Amaz.Map()
            algoMap:set(FACE_ID, id)
            algoMap:set(FACE_INDEX, index)
            algoMap:set(FACE_DIRECT, self:getFaceAngle(baseInfo))
            algoMap:set(FACE_BBOX, self:getFaceBBox(baseInfo.rect, self.makeupRenderer.mesh, index * 248))
            faceAlgoParams:pushBack(algoMap)
        end
    end
    local freidCount = result:getFreidInfoCount()
    if freidCount > self.maxDisplayNum then
        faceCountExceedMax = true
    end
    self.scriptProps:set(FACE_INFO, faceAlgoParams)
    self.scriptProps:set(FACE_COUNT_EXCEED_MAX, faceCountExceedMax)
    -- Amaz.LOGW(self.logTag, "onLateUpdate face algo params size " .. faceAlgoParams:size())
end

function smooth:onEvent(comp, event)
    if event.type == Amaz.AppEventType.SetEffectIntensity then
        self:handleIntensityEvent(comp, event)
    end
end

function smooth:handleIntensityEvent(comp, event)
    if event.args:get(0) == FACE_ADJUST then
        self.faceAdjustMaps = {}
        local inputVector = event.args:get(1)
        local inputSize = inputVector:size()
        for i = 0, inputSize - 1 do
            local inputMap = inputVector:get(i)
            local inputId = inputMap:get(FACE_ID)
            self.faceAdjustMaps[inputId] = inputMap
        end
    end
end

function smooth:getFaceAngle(info)
    local vector = Amaz.FloatVector()
    vector:pushBack(info.yaw)
    vector:pushBack(info.pitch)
    vector:pushBack(info.roll)
    return vector
end

function smooth:getFaceBBox(rect, mesh, offset)
    local min_x = rect.x * 2 - 1 -- left
    local min_y = rect.y * 2 - 1 -- bottom
    local max_x = (rect.x + rect.width) * 2 - 1 -- right
    local max_y = (rect.y + rect.height) * 2 - 1 -- top
    if mesh:getVertexCount() ~= 0 then
        local point0_indexs = { 113, 113, 49, 0, 32, 5, 27, 12, 20, 16 }
        local point1_indexs = { 106, 112, 43, 106, 112, 107, 111, 108, 110, 109 }
        local lerp_ratios = { 0.5, 0.5, 3, 0.5, 0.5, 0.35, 0.35, 0.2, 0.2, 0.2 }
        local point0, point1, vertex, x, y
        for i = 1, 10 do
            point0 = mesh:getVertex(point0_indexs[i] + offset)
            point1 = mesh:getVertex(point1_indexs[i] + offset)
            vertex = point0:lerp(point1, lerp_ratios[i])
            x = vertex.x * 2 / self.inputWidth - 1
            y = 1 - vertex.y * 2 / self.inputHeight
            min_x = MIN(min_x, x)
            min_y = MIN(min_y, y)
            max_x = MAX(max_x, x)
            max_y = MAX(max_y, y)
        end
    end

    local vector = Amaz.FloatVector()
    vector:pushBack(MAX(min_x, -1)) -- left
    vector:pushBack(MIN(max_y, 1)) -- top
    vector:pushBack(MIN(max_x, 1)) -- right
    vector:pushBack(MAX(min_y, -1)) -- bottom
    return vector
end

function smooth:updateFaceInfoBySize()
    self.faceInfoBySize = {}

    local result = Amaz.Algorithm.getAEAlgorithmResult()
    local faceCount = result:getFaceCount()
    local freidCount = result:getFreidInfoCount()
    -- Amaz.LOGW(self.logTag, "updateFaceInfoBySize faceCount " .. faceCount .. " freidCount " .. freidCount)
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
        -- Amaz.LOGW(self.logTag, "updateFaceInfoBySize add face info index " .. i .. " id " .. trackId .. " size " .. faceSize)
    end
    table.sort(self.faceInfoBySize, function(a, b)
        return a.size > b.size
    end)
end

exports.smooth = smooth
return exports