local print = function(...)
    local arg = {...}
    local msg = "effect_lua:"
    for k, v in pairs(arg) do
        msg = msg .. tostring(v) .. " "
    end
    -- EffectSdk.LOG_LEVEL(6, "algolua" .. msg)
end

local graph_name2amaz_scene = function(this, path)
    local feature = this:getFeature(path)
    local amazingfeature = EffectSdk.castAmazingFeature(feature)
    if (not amazingfeature) then
        return false
    end
    local swigScene = amazingfeature:getAMGScene()
    if (not swigScene) then
        return false
    end
    -- get AMG Scene
    local scene = Amaz.AmazingUtil.SWIGToAMGObj(swigScene)
    if (scene == nil or scene.name == nil) then
        return false
    end
    -- store effectName in scene
    scene.name = this:getName()
    return true
end

EventHandles = {
    onUpdate = function(this, delta_time)
        graph_name2amaz_scene(this, "AmazingFeature/")
    end,
}
