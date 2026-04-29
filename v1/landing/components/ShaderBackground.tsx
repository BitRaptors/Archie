"use strict";
"use client";

import { ShaderGradientCanvas, ShaderGradient } from "shadergradient";

export function ShaderBackground() {
    const gradientProps: any = {
        animate: "on",
        axesHelper: "off",
        brightness: 1.2,
        cAzimuthAngle: 180,
        cDistance: 3.6,
        cPolarAngle: 90,
        cameraZoom: 1,
        color1: "#023047",
        color2: "#219ebc",
        color3: "#fb8500",
        destination: "onCanvas",
        embedMode: "off",
        envPreset: "lobby",
        format: "gif",
        fov: 45,
        frameRate: 10,
        gizmoHelper: "hide",
        grain: "on",
        lightType: "env",
        pixelDensity: 1,
        positionX: -1.4,
        positionY: 0,
        positionZ: 0,
        range: "disabled",
        rangeEnd: 40,
        rangeStart: 0,
        reflection: 0.1,
        rotationX: 0,
        rotationY: 10,
        rotationZ: 50,
        shader: "defaults",
        type: "plane",
        uAmplitude: 1,
        uDensity: 1.3,
        uFrequency: 5.5,
        uSpeed: 0.2,
        uStrength: 4,
        uTime: 0,
        wireframe: false,
    };

    return (
        <div className="absolute inset-0 z-0">
            <ShaderGradientCanvas
                style={{
                    position: "absolute",
                    top: 0,
                }}
            >
                <ShaderGradient {...gradientProps} />
            </ShaderGradientCanvas>
            <div className="absolute inset-0 z-1 bg-gradient-to-b from-transparent to-deep-space-blue opacity-60"></div>
        </div>
    );
}
