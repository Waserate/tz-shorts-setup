local exports = exports or {}
local ClarityAndFoundation = ClarityAndFoundation or {}
ClarityAndFoundation.__index = ClarityAndFoundation

function ClarityAndFoundation.new(construct, ...)
    local self = setmetatable({}, ClarityAndFoundation)
    self.comps = {}
    self.compsdirty = true
    
    
    self.inputTex = nil

    self.commandBufDynamic = Amaz.CommandBuffer()
    self.commandBufStaticOddFrame = Amaz.CommandBuffer() 
    self.commandBufStaticEvenFrame = Amaz.CommandBuffer() 

    -- common for clarity and foundation
    self.facewarpMaterial = nil
    self.facewarpMaterialBlockEven = Amaz.MaterialPropertyBlock()
    self.facewarpMaterialBlockOdd = Amaz.MaterialPropertyBlock()
    -- clarity
    self.prefusionMaterial = nil
    self.prefusionMaterialBlock = Amaz.MaterialPropertyBlock()
    -- common for clarity and foundation
    self.fusionMaterial = nil
    self.fusionMaterialBlock = Amaz.MaterialPropertyBlock()

    -- common for clarity and foundation
    self.facewarpRT = nil
    -- clarity
    self.prefusionRT = nil
    self.lastprefusionRT = nil
    -- common for clarity and foundation
    self.outputRT = nil

    self.width = 720
    self.height = 1280

    self.meshUpdateTool = nil
    self.facewarpMesh = nil
    self.meshType = Amaz.AMGBeautyMeshType.FACE145
    self.submeshIndicesCount = 768

    self.identityMatrix = Amaz.Matrix4x4f()

    self.clearIntensity = 0.0
    self.exclusiveFlag = false

    -- common for clarity and foundation
    self.isFirstFrame = true
    self.isOddFrame = true -- start from 1
    return self
end

function ClarityAndFoundation:initialize(sys)
    local commandTableResources = sys.scene:findEntityBy("ClarityAndFoundation"):getComponent("TableComponent")

    -- mesh and AMGFaceMeshUtils object (will be used to update mesh vertices)
    self.facewarpMesh = commandTableResources.table:get("facewarp_mesh") 
    if self.facewarpMesh ~= nil then
        self.meshUpdateTool = Amaz.AMGFaceMeshUtils()
        self.meshUpdateTool:setMesh(self.facewarpMesh, self.meshType)
    end

    -- INPUT0
    self.inputTex = commandTableResources.table:get("input_texture")

    -- camera input width and height
    self.width = self.inputTex.width
    self.height = self.inputTex.height

    -- material
    self.facewarpMaterial = commandTableResources.table:get("facewarp_material")
    self.prefusionMaterial = commandTableResources.table:get("prefusion_material")
    self.fusionMaterial = commandTableResources.table:get("fusion_material")

    -- render target
    self.facewarpRT = commandTableResources.table:get("facewarp_rt")
    self.prefusionRT = commandTableResources.table:get("prefusion_rt")
    self.lastprefusionRT = commandTableResources.table:get("lastprefusion_rt")
    self.outputRT = commandTableResources.table:get("output_rt")  --output

    -- model matrix and mvp matrix
    self.identityMatrix:SetIdentity()

    local mvpMatrix = Amaz.Matrix4x4f()
    mvpMatrix:SetTranslate(Amaz.Vector3f(-1, -1, 0))
    mvpMatrix:Scale(Amaz.Vector3f(2, 2, 1))
    mvpMatrix:Translate(Amaz.Vector3f(0, 1, 0))
    mvpMatrix:Scale(Amaz.Vector3f(1, -1, 1))
    mvpMatrix:Scale(Amaz.Vector3f(1.0 / self.width, 1.0 / self.height, 1))
    self.facewarpMaterialBlockEven:setMatrix("uMVPMatrix", mvpMatrix)
    self.facewarpMaterialBlockOdd:setMatrix("uMVPMatrix", mvpMatrix)

    -- disable depth rt
    local outputRT = sys.scene:getOutputRenderTexture()
    outputRT.attachment = Amaz.RenderTextureAttachment.NONE

    -- clear irrelevant events
    local scriptSys = sys.scene:getSystem("ScriptSystem")
    scriptSys:clearAllEventType()
    scriptSys:addEventType(Amaz.AppEventType.SetEffectIntensity)
end

function ClarityAndFoundation:initializeOddFrame(sys)
    --facewarp -- pass 1
    self.commandBufStaticOddFrame:setRenderTexture(self.facewarpRT)
    self.commandBufStaticOddFrame:clearRenderTexture(true, true, Amaz.Color(0.0, 0.0, 0.0, 0.0))
    self.commandBufStaticOddFrame:drawMesh(self.facewarpMesh, self.identityMatrix, self.facewarpMaterial, 0, 0, self.facewarpMaterialBlockOdd, true)  -- output: RG

    --prefusion -- pass 2
    self.prefusionMaterial:setTex("lastGradimage", self.lastprefusionRT)
    self.commandBufStaticOddFrame:blitWithMaterialAndProperties(self.inputTex, self.prefusionRT, self.prefusionMaterial, 0, self.prefusionMaterialBlock, true)    -- output: RG

    --fusion -- pass 7
    self.commandBufStaticOddFrame:setRenderTexture(self.outputRT)
    self.commandBufStaticOddFrame:clearRenderTexture(true, true, Amaz.Color(0.0, 0.0, 0.0, 0.0))
    self.fusionMaterial:setTex("faceMask", self.facewarpRT) 
    self.fusionMaterial:setTex("newGradimage", self.prefusionRT) 
    self.commandBufStaticOddFrame:blitWithMaterialAndProperties(self.inputTex, self.outputRT, self.fusionMaterial, 0, self.fusionMaterialBlock, true) -- output: RGBA
end

function ClarityAndFoundation:initializeEvenFrame(sys)
    --facewarp -- pass 1
    self.commandBufStaticEvenFrame:setRenderTexture(self.facewarpRT)
    self.commandBufStaticEvenFrame:clearRenderTexture(true, true, Amaz.Color(0.0, 0.0, 0.0, 0.0))
    self.commandBufStaticEvenFrame:drawMesh(self.facewarpMesh, self.identityMatrix, self.facewarpMaterial, 0, 0, self.facewarpMaterialBlockEven, true)  -- output: RG

    --prefusion -- pass 2
    self.prefusionMaterial:setTex("lastGradimage", self.prefusionRT)
    self.commandBufStaticEvenFrame:blitWithMaterialAndProperties(self.inputTex, self.lastprefusionRT, self.prefusionMaterial, 0, self.prefusionMaterialBlock, true)    -- output: RG

    --fusion -- pass 7
    self.commandBufStaticEvenFrame:setRenderTexture(self.outputRT)
    self.commandBufStaticEvenFrame:clearRenderTexture(true, true, Amaz.Color(0.0, 0.0, 0.0, 0.0))
    self.fusionMaterial:setTex("faceMask", self.facewarpRT) 
    self.fusionMaterial:setTex("newGradimage", self.lastprefusionRT) 
    self.commandBufStaticEvenFrame:blitWithMaterialAndProperties(self.inputTex, self.outputRT, self.fusionMaterial, 0, self.fusionMaterialBlock, true) -- output: RGBA
end

function ClarityAndFoundation:onStart(sys)

    self:initialize(sys)

    self:initializeOddFrame(sys)
    self:initializeEvenFrame(sys)
end

function ClarityAndFoundation:onUpdate(sys,deltaTime)
    if self.exclusiveFlag then
        -- been exclusived, simply blit 
        self.commandBufDynamic:clearAll()
        self.commandBufDynamic:setRenderTexture(self.outputRT)
        self.commandBufDynamic:clearRenderTexture(true, true, Amaz.Color(0.0, 0.0, 0.0, 0.0))
        self.commandBufDynamic:blit(self.inputTex, self.outputRT)
        sys.scene:commitCommandBuffer(self.commandBufDynamic)
        return
    end

    local width = self.inputTex.width
    local height = self.inputTex.height
    if width ~= self.width or height ~= self.height then
        Amaz.LOGI("ClarityAndFoundation", "ClarityAndFoundation:onUpdate resolution changed")
        self.width = width
        self.height = height

        local mvpMatrix = Amaz.Matrix4x4f()
        mvpMatrix:SetTranslate(Amaz.Vector3f(-1, -1, 0))
        mvpMatrix:Scale(Amaz.Vector3f(2, 2, 1))
        mvpMatrix:Translate(Amaz.Vector3f(0, 1, 0))
        mvpMatrix:Scale(Amaz.Vector3f(1, -1, 1))
        mvpMatrix:Scale(Amaz.Vector3f(1.0 / self.width, 1.0 / self.height, 1))
        self.facewarpMaterialBlockEven:setMatrix("uMVPMatrix", mvpMatrix)
        self.facewarpMaterialBlockOdd:setMatrix("uMVPMatrix", mvpMatrix)

        -- update sampler steps
        self.prefusionMaterialBlock:setVec2("imagestep", Amaz.Vector2f(1.0 / self.width, 1.0 / self.height))
        self.fusionMaterialBlock:setVec2("imagestep", Amaz.Vector2f(1.0 / self.width, 1.0 / self.height))
    end

    -- update face data
    local result =  Amaz.Algorithm:getAEAlgorithmResult()
    local faceCount = 0
    local curfaceid = {}
    if result ~= nil then
        faceCount = result:getFaceCount()
        for i = 0, faceCount-1 do
            local face106Points = result:getFaceBaseInfo(i).points_array
            curfaceid[i] = result:getFaceBaseInfo(i).ID
            self.meshUpdateTool:updateMeshWithFaceData106(self.meshType, face106Points, i)
        end
        self.facewarpMesh:getSubMesh(0).indicesCount = faceCount * self.submeshIndicesCount
    end


    -- update uniforms
    if self.isFirstFrame then
        self.prefusionMaterialBlock:setFloat("frameindex", 0.0)
        self.isFirstFrame = false
    else
        self.prefusionMaterialBlock:setFloat("frameindex", 1.0)
    end
    self.fusionMaterialBlock:setFloat("clearIntensity", self.clearIntensity)
    
    if self.clearIntensity > 0.0 then
        -- sharp intensity not 0 
        if self.isOddFrame then
            self.prefusionMaterial:setTex("lastGradimage", self.lastprefusionRT)
            self.fusionMaterial:setTex("newGradimage", self.prefusionRT) 
            sys.scene:commitCommandBuffer(self.commandBufStaticOddFrame)
            self.isOddFrame = false --reset for next frame
        else
            self.prefusionMaterial:setTex("lastGradimage", self.prefusionRT)
            self.fusionMaterial:setTex("newGradimage", self.lastprefusionRT) 
            sys.scene:commitCommandBuffer(self.commandBufStaticEvenFrame)
            self.isOddFrame = true  --reset for next frame
        end
    else
        -- sharp is 0, simply blit
        self.commandBufDynamic:clearAll()
        self.commandBufDynamic:setRenderTexture(self.outputRT)
        self.commandBufDynamic:clearRenderTexture(true, true, Amaz.Color(0.0, 0.0, 0.0, 0.0))
        self.commandBufDynamic:blit(self.inputTex, self.outputRT)
        sys.scene:commitCommandBuffer(self.commandBufDynamic)
    end
end

function ClarityAndFoundation:onEvent(sys,event)
    if event.type == Amaz.AppEventType.SetEffectIntensity then
        if "intensity" == event.args:get(0) then
            local intensity = event.args:get(1)
            self.clearIntensity = intensity
        end
    end
end
exports.ClarityAndFoundation = ClarityAndFoundation
return exports
