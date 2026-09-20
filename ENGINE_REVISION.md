# Film Look Studio — source-aware engine revision

This revision starts from `film-look-studio-part-1-project`. The supplied combined migration bundle, attached Replit briefs, historical camera outputs and existing v1.2 archive were reference material. They were not treated as instructions to overwrite the current product. Original Downloads folders remain unchanged.

## Why the previous output differed

1. The catalog selected `ColorMatrix1` and `ProfileToneCurve` for DCPs. The actual hue/saturation/value tables were declared unsupported. This discarded important film-specific color information while applying a raw camera matrix to already-rendered RGB.
2. The older `smart-cube` path summarized source metadata into six broad adjustments. Its fallback parsed words; it did not evaluate the uploaded source's color transform.
3. The editor's default controls already applied exposure/contrast, shadow lift, several color grades, toe/shoulder shaping and saturation changes. Opening a finished LUT therefore added another grade.
4. Unsupported nodes could be skipped while a CUBE or camera package was still downloadable. The UI displayed READY for any status object, including an error result.
5. Serial opacity blending was the only combination method. It is not a weighted mixture of independently evaluated source transforms.
6. Direct image rendering used 16-bit integer indices, which can overflow for larger CUBEs. Leica serialization reset non-unit domains without baking their mapping. Hald data were reduced to 8-bit and incorrectly passed back through the CUBE text parser.
7. Tonal color grades used abrupt masks and hue rotation rather than a smooth color bias. Monochrome conversion could occur only at package export, differing from the preview.

## What is implemented

- Neutral editor defaults, plus a Neutral controls action for older workspaces.
- DCP hue/saturation/value tables: all three axes, hue wrap, both illuminants, declared value encoding, shape checks and finite-data checks. Table storage follows V/H/S order. The default creative component applies a bounded, smoothed display adaptation. Camera calibration matrices are excluded; absolute profile tone curves are optional separate components.
- An optional same-calibration baseline DCP can be selected for relative hue differences and saturation/value ratios. This is a useful creative approximation, not unique separation of sensor calibration from film response.
- LRTemplate/XMP string, numeric and curve parsing. Selected HSL changes are implemented with restrained strengths; curves can be enabled explicitly. CameraProfile is retained for pairing. Adobe calibration, local adjustments, grain, exposure processing and other unsupported settings are identified as omitted, not reconstructed.
- Separate sequential stack and normalized weighted source-mixture modes. Source strengths become mixture weights; finishing controls follow the mixture.
- One numerical CUBE sampler for graph, preview and domain-aware Leica export. Large indices use int64. Hald TIFF precision is preserved, with an explicit Hald import selector. Embedded photo ICC profiles convert to sRGB for software preview.
- Smooth tonal color grading, selective hue adjustments, monochrome preview/export consistency and chroma compression for the new source adaptations.
- Unsupported active components block export. Disabled components do not. Raw calibration components cannot enter the rendered-RGB pipeline. Recognized F-Log sources are blocked until an appropriate normalization is supplied; they are not silently treated as sRGB.
- Reference photographs receive scene-dependent tone/color statistics and can be attached to a creative brief. They are not interpreted as LUTs.
- Optional creative assistant: sends the requested direction, source identities, layer settings and up to twelve selected reference thumbnails to the configured model. It returns a bounded set of editable graph operations, which are compiled before presentation. Apply/discard and undo remain user-controlled. No model-generated LUT rows or code are executed. Missing credentials produce an explicit unavailable message.
- Downloaded Look packages include recipe.json, source identities/hashes, the engine report, and updated checksums. Source profile binaries are not added to those exports. Existing Leica payload generation and injector transport remain unchanged.

## Replit handoff

Use this project revision as code, preserving your existing Replit secrets, database and saved workspaces. Do not replace a live database with a local copy. The download excludes runtime databases and secrets.

1. Install Python dependencies from requirements.txt (Replit's existing Python 3.11 configuration is appropriate).
2. Run `npm ci`, `npm run typecheck`, and `npm run build`.
3. Retain your existing DATABASE_URL and Clerk configuration. The sign-in architecture was not changed.
4. For creative proposals, set ANTHROPIC_API_KEY and CREATIVE_ASSISTANT_MODEL to a model available in your account that supports images. No particular model is silently assumed. Manual source building requires no model key.
5. Start with `bash scripts/run.sh`, or `python main.py`. Existing production launch settings are retained.
6. In an old workspace, use Neutral controls before judging the source alone. Reselect older DCP catalog bases so they use CreativeInterpretation rather than ColorMatrix1. Old calibration nodes deliberately report an error instead of producing bad color.
7. For PNG/TIFF LUTs choose Hald LUT image before ingesting. Ordinary photographs remain references. For a paired preset, add its CameraProfile DCP separately; it is not embedded in a develop preset.
8. Compare on several neutral input photographs, including skin, before deciding that an artistic recipe is ready for camera use.

The included 95 MB source-library archive is your supplied reference library. Keep it private unless you have distribution rights. It is not needed in a patch applied to a project that already has the same archive.

## Verification and limits

Numerical regression checks cover all nine v1.2 LUTs, actual M9 DCPs, table axes and wrapping, self-baseline identity, weighted mixtures, XMP settings, 16-bit Hald precision, large CUBE indexing, non-unit domains, malformed values, smooth grading, and monochrome parity. HTTP checks import DCP/Hald sources, compile, preview and package them; software preview is compared with rendering the exported CUBE. Existing payload/injector regression checks are retained.

This is an engineering correction and an editable interpretation engine, not a claim to reproduce every raw developer or film stock. It does not recreate our nine recipes from their names. Those finished CUBEs serve as numerical regression references. A calibrated RAW workflow, arbitrary log input conversions, local image effects, grain and exact Lightroom process emulation remain outside this implementation. A single reference photograph cannot identify a unique film transform. The assistant's model/network path needs your configured account; local validation uses mocked model responses. The signed-in Replit deployment and camera appearance were not verified here.

DNG terminology/reference: [Adobe DNG SDK source](https://android.googlesource.com/platform/external/dng_sdk/+/refs/heads/master/source/dng_camera_profile.h) and [Apple Image I/O DNG table encoding documentation](https://developer.apple.com/documentation/imageio/kcgimagepropertydngprofilehuesatmapencoding). Display-space adaptation parameters are this project's artistic choices, not prescriptions from those specifications.
