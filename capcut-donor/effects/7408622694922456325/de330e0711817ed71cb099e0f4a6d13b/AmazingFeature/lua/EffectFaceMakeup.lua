local exports = exports or {}

local EffectFaceMakeup = EffectFaceMakeup or {}
EffectFaceMakeup.__index = EffectFaceMakeup

local FACE_ADJUST_COLDWARM = "face_adjust_skin_ColdWarm"
local FACE_ADJUST_INTENSITY = "face_adjust_skin_Intensity"
local FACE_ID = "id"
local INTENSITY_TAG = "intensity"

local EPSC = 0.001

local COLDWARM_DEFAULT = 0
local INTENSITY_DEFAULT = 0

function EffectFaceMakeup.new(construct, ...)
    local self = setmetatable({}, EffectFaceMakeup)

    if construct and EffectFaceMakeup.constructor then
        EffectFaceMakeup.constructor(self, ...)
    end

    self.faceAdjustMaps = {}

    self.faceAdjustMaps[FACE_ADJUST_COLDWARM] = COLDWARM_DEFAULT
    self.faceAdjustMaps[FACE_ADJUST_INTENSITY] = INTENSITY_DEFAULT

    return self
end

function EffectFaceMakeup:constructor()
end

function EffectFaceMakeup:onStart(comp)
    local scene = comp.entity.scene
    self.femaleOpacity = 0
    self.maleOpacity = 0

    self.makeupEntity = scene:findEntityBy("mask")
    self.makeupComp = self.makeupEntity:getComponent("EffectFaceMakeupFaceU")
    self.makeupRenderer = self.makeupEntity:getComponent("MeshRenderer")
    self.skinSegEntity = scene:findEntityBy("skinSegment")
    self.skinSegRenderer = self.skinSegEntity:getComponent("MeshRenderer")

    self.skinColorEntity = scene:findEntityBy("skinColor")

end


function EffectFaceMakeup:onUpdate(comp, deltaTime)
    -- set coldWarmIntensity and intensity
    local intensity = self.faceAdjustMaps[FACE_ADJUST_INTENSITY]
    local coldWarmIntensity = self.faceAdjustMaps[FACE_ADJUST_COLDWARM]

    --set 
    self.skinSegRenderer.material:setFloat("coldWarmIntensity", coldWarmIntensity)
    self.skinSegRenderer.material:setFloat("intensity", intensity)

    -- coldWarmIntensity [-0.5,0.5]  intensity [0,1]
    local isVisible = false
    if intensity > EPSC or coldWarmIntensity > EPSC  or coldWarmIntensity < -1 * EPSC then
        isVisible = true
    end

    self.skinColorEntity.visible = isVisible

    --Amaz.LOGI("face_adjust_skin", "coldWarmIntensity:" .. coldWarmIntensity)
    --Amaz.LOGI("face_adjust_skin", "intensity:" .. intensity)
end


function EffectFaceMakeup:onEvent(sys, event)
    if event.type == Amaz.AppEventType.SetEffectIntensity then
        self:handleIntensityEvent(event)
    end
end

function EffectFaceMakeup:handleIntensityEvent(event)
    local key = event.args:get(0)
    if key == FACE_ADJUST_COLDWARM  or  key == FACE_ADJUST_INTENSITY then
        --self.faceAdjustMaps[key] = event.args:get(1)
        local intensityMap = {}

        local inputVector = event.args:get(1)
        local inputSize = inputVector:size()
        for i = 0, inputSize - 1 do
           local inputMap = inputVector:get(i)
           local inputId = inputMap:get(FACE_ID)
           intensityMap[inputId] = inputMap
        end

        local adjustMap = intensityMap[0]  --The face_adjust_skin sticker work on all the skins id:-1 (id:0 for debug)
        if adjustMap == nil then
            adjustMap = intensityMap[-1]
        end
        if adjustMap ~= nil then
            local intensity = adjustMap:get(INTENSITY_TAG)
            self.faceAdjustMaps[key] = intensity
            --Amaz.LOGI("face_adjust_skin", "set intensity event key:" .. key .." intensity: " .. intensity)
        end
    end
end

exports.EffectFaceMakeup = EffectFaceMakeup

return exports
