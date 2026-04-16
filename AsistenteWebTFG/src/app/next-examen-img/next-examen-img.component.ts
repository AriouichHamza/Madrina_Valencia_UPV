
import { Component, OnInit, Input, SimpleChanges, OnChanges } from '@angular/core';

@Component({
    selector: 'app-next-examen-img',
    templateUrl: './next-examen-img.component.html',
    styleUrls: ['./next-examen-img.component.scss']
})




export class NextExamenImg implements OnInit, OnChanges {

    ImageNextExamen: string = '';
    @Input() containerHeight: number = 0;

    w: number = 0;
    h: number = 0;
    bw: number = 0;

    img: any = null;

    move: boolean = false;
    visible: boolean = false;

    constructor() { }

    ngOnInit(): void {

    }

    ngOnChanges(changes: SimpleChanges): void {

        return;


    }

    changeImage(image : string) {
        this.cropImg(image).then((img) => {
            this.ImageNextExamen = img;
        });
    }
    cropImg(image : string): Promise<string>{
        return new Promise(resolve => {
            let img = new Image();
            img.src = image;
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const cropHeight = img.height*0.3;
                const cropWidth = img.width*0.6;
                canvas.width = cropWidth;
                canvas.height = cropHeight;
                if(!ctx) {
                    return;
                }
                ctx.drawImage(img, img.width - cropWidth, 0, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
                resolve(canvas.toDataURL());
            }
        }
        )
    }



}
