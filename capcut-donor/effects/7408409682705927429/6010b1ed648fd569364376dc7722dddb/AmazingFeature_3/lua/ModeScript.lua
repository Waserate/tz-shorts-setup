--@input float curTime = 0.0{"widget":"slider","min":0,"max":3.0}
local exports = exports or {}
local ModeScript = ModeScript or {}
ModeScript.__index = ModeScript
function ModeScript.new(construct, ...)
    local self = setmetatable({}, ModeScript)
    if construct and ModeScript.constructor then ModeScript.constructor(self, ...) end
    self.startTime = 0.0
    self.endTime = 3.0
    self.curTime = 0.0
    self.first = nil
    return self
end

function ModeScript:constructor()
end

-- function ModeScript:onUpdate(comp, detalTime)

-- end

function ModeScript:onStart(comp)

    self.Material = comp.entity.scene:findEntityBy("Untitled"):getComponent("MeshRenderer").material
end


function ModeScript:onEvent(comp, event)
    if event.type == Amaz.AppEventType.SetEffectIntensity then
        if "intensity" == event.args:get(0) then
            local intensity = event.args:get(1)
            self.Material:setFloat("uniAlpha",intensity)
        end
    end
end

exports.ModeScript = ModeScript
return exports