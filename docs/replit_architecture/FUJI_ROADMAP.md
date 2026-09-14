# Fuji Roadmap

## Phase A: recipe representation

Start with Fujifilm X-E5 and GFX50R. Build exact capability profiles. The recipe system should support only controls actually offered by the selected body.

Potential fields: film simulation, dynamic range, highlight, shadow, color, sharpness, noise reduction, clarity, grain, Color Chrome, Color Chrome Blue, white balance mode, red shift, blue shift.

## Cross-camera matching

A Look such as IA Presence should have sibling implementations. The Fuji implementation is not a random 'similar recipe'; it is a constrained approximation of the master Look intent using Fuji controls.

Useful comparison dimensions: tone curve, hue distribution, chroma distribution, shadow/highlight color, selected patches, Delta E where appropriate, perceptual image similarity.

## Phase B: native camera processing

The long-term target is to use a connected Fuji camera as the native RAF development engine, similar in purpose to X RAW Studio.

Workflow:

RAF -> Photo Lab Look -> Fuji parameter translation -> local bridge -> Fuji native development -> camera output -> Photo Lab derivative/storage.

## Protocol Lab method

Use identical RAF input and vary exactly one camera-processing parameter between runs. Diff protocol traffic and output. Store camera model, firmware, source checksum, parameter delta, trace, and output checksum.
