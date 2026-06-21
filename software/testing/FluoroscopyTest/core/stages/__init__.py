from .fisheye_correction import FisheyeCorrection
from .crop import Crop
from .grayscale import Grayscale
from .image_overlay import ImageOverlay
from .color_mask import ColorMask
from .mask_combine import MaskCombine
from .mask_apply import MaskApply
from .vignette import Vignette
from .field_mask import FieldMask
from .grain import Grain
from .transform import Transform
from .downsample import Downsample
from .upsample import Upsample

STAGE_REGISTRY: dict[str, type] = {
    FisheyeCorrection.stage_name: FisheyeCorrection,
    Crop.stage_name: Crop,
    Grayscale.stage_name: Grayscale,
    ImageOverlay.stage_name: ImageOverlay,
    ColorMask.stage_name: ColorMask,
    MaskCombine.stage_name: MaskCombine,
    MaskApply.stage_name: MaskApply,
    Vignette.stage_name: Vignette,
    FieldMask.stage_name: FieldMask,
    Grain.stage_name: Grain,
    Transform.stage_name: Transform,
    Downsample.stage_name: Downsample,
    Upsample.stage_name: Upsample,
}
