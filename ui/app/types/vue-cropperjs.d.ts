declare module 'vue-cropperjs' {
    interface CropperData {
        x: number;
        y: number;
        width: number;
        height: number;
        rotate: number;
        scaleX: number;
        scaleY: number;
    }

    interface CropperOptions {
        aspectRatio?: number;
        viewMode?: number;
        dragMode?: 'crop' | 'move' | 'none';
        autoCropArea?: number;
        background?: boolean;
        responsive?: boolean;
        restore?: boolean;
        checkCrossOrigin?: boolean;
        checkOrientation?: boolean;
        modal?: boolean;
        guides?: boolean;
        center?: boolean;
        highlight?: boolean;
        cropBoxMovable?: boolean;
        cropBoxResizable?: boolean;
        toggleDragModeOnDblclick?: boolean;
        minCanvasWidth?: number;
        minCanvasHeight?: number;
        minCropBoxWidth?: number;
        minCropBoxHeight?: number;
        minContainerWidth?: number;
        minContainerHeight?: number;
        ready?: () => void;
        cropstart?: (event: CustomEvent) => void;
        cropmove?: (event: CustomEvent) => void;
        cropend?: (event: CustomEvent) => void;
        crop?: (event: CustomEvent) => void;
        zoom?: (event: CustomEvent) => void;
    }

    interface VueCropperInstance {
        getCroppedCanvas(options?: {
            width?: number;
            height?: number;
            minWidth?: number;
            minHeight?: number;
            maxWidth?: number;
            maxHeight?: number;
            fillColor?: string;
            imageSmoothingEnabled?: boolean;
            imageSmoothingQuality?: 'low' | 'medium' | 'high';
        }): HTMLCanvasElement;
        getData(rounded?: boolean): CropperData;
        setData(data: Partial<CropperData>): void;
        crop(): void;
        clear(): void;
        replace(url: string, hasSameSize?: boolean): void;
        enable(): void;
        disable(): void;
        destroy(): void;
        move(offsetX: number, offsetY?: number): void;
        moveTo(x: number, y?: number): void;
        zoom(ratio: number): void;
        zoomTo(ratio: number, pivotX?: number, pivotY?: number): void;
        rotate(degree: number): void;
        rotateTo(degree: number): void;
        scale(scaleX: number, scaleY?: number): void;
        scaleX(scaleX: number): void;
        scaleY(scaleY: number): void;
        reset(): void;
    }

    const VueCropper: DefineComponent<
        {
            src?: string;
            alt?: string;
            imgStyle?: Record<string, any>;
            aspectRatio?: number;
            viewMode?: number;
            dragMode?: 'crop' | 'move' | 'none';
            autoCropArea?: number;
            background?: boolean;
            responsive?: boolean;
            restore?: boolean;
            checkCrossOrigin?: boolean;
            checkOrientation?: boolean;
            modal?: boolean;
            guides?: boolean;
            center?: boolean;
            highlight?: boolean;
            cropBoxMovable?: boolean;
            cropBoxResizable?: boolean;
            toggleDragModeOnDblclick?: boolean;
            minCanvasWidth?: number;
            minCanvasHeight?: number;
            minCropBoxWidth?: number;
            minCropBoxHeight?: number;
            minContainerWidth?: number;
            minContainerHeight?: number;
            ready?: () => void;
            cropstart?: (event: CustomEvent) => void;
            cropmove?: (event: CustomEvent) => void;
            cropend?: (event: CustomEvent) => void;
            crop?: (event: CustomEvent) => void;
            zoom?: (event: CustomEvent) => void;
        },
        {},
        {},
        {},
        {},
        {},
        {},
        {},
        true,
        {},
        {},
        VueCropperInstance
    >;

    export default VueCropper;
}
