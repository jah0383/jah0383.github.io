let distinct_colors = ["#FFFF00",
                       "#1CE6FF", "#FF34FF", "#FF4A46", "#008941", "#006FA6", "#A30059","#FFDBE5", "#7A4900", "#0000A6", "#63FFAC", "#B79762", "#004D43", "#8FB0FF", "#997D87","#5A0007", "#809693", "#FEFFE6", "#1B4400", "#4FC601", "#3B5DFF", "#4A3B53", "#FF2F80", "#61615A", "#BA0900", "#6B7900", "#00C2A0", "#FFAA92", "#FF90C9", "#B903AA", "#D16100","#DDEFFF", "#000035", "#7B4F4B", "#A1C299", "#300018", "#0AA6D8", "#013349", "#00846F","#372101", "#FFB500", "#C2FFED", "#A079BF", "#CC0744", "#C0B9B2", "#C2FF99", "#001E09"]

class Gear {
  constructor(radius, points,pradius) {
    this.radius = radius;
    this.points = points;
    this.pradius = 10;
  }
  
  
  draw(lineup=0){
    noStroke();
    fill("#FFFFFF")
    ellipse(0,0,this.radius*2);
    for(let step = 0; step<this.points;step++){
      let angle = step*(360.0/this.points)+ lineup;
      let dcol_index = Math.floor((step/this.points) * distinct_colors.length);
      fill(distinct_colors[dcol_index]);

      var x = this.radius * cos(angle);
      var y = this.radius * sin(angle);

      ellipse(x, y, 4*this.radius/this.points);      
    }

  }
}