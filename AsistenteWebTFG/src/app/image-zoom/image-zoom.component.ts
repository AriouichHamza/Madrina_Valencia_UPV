import { Component, Input, OnChanges, OnInit, SimpleChanges } from '@angular/core';

@Component({
  selector: 'app-image-zoom',
  templateUrl: './image-zoom.component.html',
  styleUrls: ['./image-zoom.component.scss']
})
export class ImageZoomComponent implements OnInit, OnChanges {

  @Input() fullImage: string = '';
  @Input() containerHeight: number = 0;

  w: number = 0;
  h: number = 0;
  bw: number = 0;

  img: any = null;
  glass: any = null;

  imgID = 'imgZoom';
  glassID = 'glassZoom';
  zoom = 2;

  move: boolean = false;
  visible: boolean = false;

  constructor() { }

  ngOnInit(): void {

  }

  ngOnChanges(changes: SimpleChanges): void {

    if (document.getElementById(this.imgID) != null) {
      this.img = document.getElementById(this.imgID);
    }

    if (this.fullImage != undefined && this.fullImage.length) {
      if (this.glass != null && this.img != null) {
        this.setGlassImg();
      } else if (document.getElementById(this.glassID) != null) {
        this.glass = document.getElementById(this.glassID);
        this.setGlassImg();
      }
    }
  }

  changeVisibleGlass() {

    if (this.glass == null) return;
  
    if (this.visible) {
      let split = this.glass.style.backgroundSize.split(' ')[0];
      if (parseInt(split.substring(0, split.length - 2)) == 0) {
        this.setGlassImg();
      }
    }

    if (this.visible && this.move) {
      this.move = false;
    } else if (this.visible && !this.move) {
      this.visible = false;
      this.move = false;
      this.glass.style.display = 'none';
    } else if (!this.visible) {
      this.visible = true;
      this.move = true;
      this.glass.style.display = 'block';
    }    
  }

  moveMagnifier(e:any) {

    var pos, x, y;
    /* Prevent any other actions that may occur when moving over the image */
    e.preventDefault();
    /* Get the cursor's x and y positions: */

    if (!this.move) return;

    function getCursorPos(e:any, img: any) {
      var a, x = 0, y = 0;
      /* Get the x and y positions of the image: */
      a = img.getBoundingClientRect();
      /* Calculate the cursor's x and y coordinates, relative to the image: */
      x = e.pageX - a.left;
      y = e.pageY - a.top;

      return {x : x, y : y};
    }

    pos = getCursorPos(e, this.img);
    x = pos.x;
    y = pos.y;
    /* Prevent the magnifier glass from being positioned outside the image: */
    if (x > this.img.width - (this.w / this.zoom)) {x = this.img.width - (this.w / this.zoom);}
    if (x < this.w / this.zoom) {x = this.w / this.zoom;}
    if (y > this.img.height - (this.h / this.zoom)) {y = this.img.height - (this.h / this.zoom);}
    if (y < this.h / this.zoom) {y = this.h / this.zoom;}
    
    /* Set the position of the magnifier glass: */
    this.glass.style.left = (x - this.w) + "px";
    this.glass.style.top = (y - this.h) + "px";

    /* Display what the magnifier glass "sees": */
    this.glass.style.backgroundPosition = "-" + ((x * this.zoom) - this.w + this.bw) + "px -" + ((y * this.zoom) - this.h + this.bw) + "px";
  }

  private setGlassImg() {
    
    this.glass.style.backgroundImage = "url('" + this.fullImage + "')";
    this.glass.style.backgroundRepeat = "no-repeat";
    this.glass.style.backgroundSize = (this.img.width * this.zoom) + "px " + (this.img.height * this.zoom) + "px";
    this.bw = 3;
    this.w = this.glass.offsetWidth / 2;
    this.h = this.glass.offsetHeight / 2;
  }
}
