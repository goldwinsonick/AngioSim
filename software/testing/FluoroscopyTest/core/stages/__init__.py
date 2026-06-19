from .fisheye_correction import FisheyeCorrection
from .crop import Crop
from .grayscale import Grayscale
from .image_overlay import ImageOverlay

STAGE_REGISTRY: dict[str, type] = {
    FisheyeCorrection.stage_name: FisheyeCorrection,
    Crop.stage_name: Crop,
    Grayscale.stage_name: Grayscale,
    ImageOverlay.stage_name: ImageOverlay,
}
