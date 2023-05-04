let W = 800;
let H = 500;



function smooth_step(x){
  if(x<0){
    return 0;
  }
  else if(x>=0 && x<=1){
    return 3*pow(x,2) - 2*pow(x,3);
  }
  else if(x>1){
    return 1;
  }
}




function modify_4arg(func, x, x_beg, x_end, y_beg, y_end){
  return func(((x-x_beg)/(x_end-x_beg)))  * (y_end-y_beg) + y_beg;
}



//THIS IS THE MAIN FUNCTION 
function func_stairs(func, x, period, steps, amplitude, nfunc_percent, offset){
  
  let nfunc_period = period*(nfunc_percent); //Time spent flat
  let func_period = period*(1-nfunc_percent); //Time spent transitioning between flats
  let r_sum = 0;
  
  for(let i = 0; i < steps; i++){
    let half_step_period = (i*period)/steps + period/(2*steps)
    r_sum += modify_4arg(func, //Function
                (x+offset)%period, //x mod the period of the staircase
                half_step_period-func_period/steps, // Starting X
                half_step_period+func_period/steps, // Ending X
                0, 
                amplitude/steps)  
  }
  return r_sum;
}






function easeOutBounce(x){
  const n1 = 7.5625;
  const d1 = 2.75;
  if (x< 0){
    return 0;
  }
  if (x> 1){
    return 1;
  }
  if (x < 1 / d1) {
      return n1 * x * x;
  } else if (x < 2 / d1) {
      return n1 * (x -= 1.5 / d1) * x + 0.75;
  } else if (x < 2.5 / d1) {
      return n1 * (x -= 2.25 / d1) * x + 0.9375;
  } else {
      return n1 * (x -= 2.625 / d1) * x + 0.984375;
  }
}
function easeInBounce(x) {
  return 1 - easeOutBounce(1 - x);
}
function easeInOutBounce(x){
return x < 0.5 ? (1 - easeOutBounce(1 - 2 * x)) / 2 : (1 + easeOutBounce(2 * x - 1)) / 2;
}
function easeOutElastic(x){
  if(x<0){
    return 0;
  }
  const c4 = (2 * Math.PI) / 3;

  return x === 0 ? 0 : x === 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * c4) + 1;
}
function easeInOutElastic(x) {
const c5 = (2 * Math.PI) / 4.5;
  if(x<0){
    return 0;
  }
  if(x>1){
    return 1;
  }
return x === 0
  ? 0
  : x === 1
  ? 1
  : x < 0.5
  ? -(Math.pow(2, 20 * x - 10) * Math.sin((20 * x - 11.125) * c5)) / 2
  : (Math.pow(2, -20 * x + 10) * Math.sin((20 * x - 11.125) * c5)) / 2 + 1;
}
function easeInOutBack(x){
const c1 = 1.70158;
const c2 = c1 * 1.525;
  if(x<0){
    return 0;
  }
  if(x>1){
    return 1;
  }
return x < 0.5
  ? (Math.pow(2 * x, 2) * ((c2 + 1) * 2 * x - c2)) / 2
  : (Math.pow(2 * x - 2, 2) * ((c2 + 1) * (x * 2 - 2) + c2) + 2) / 2;
}

function graph(x_data, y_data,col = 0, xmod = (value) => value, ymod = (value) => value) {
  if(xmod == null){
    xmod = (value) => value;
  }
  if(ymod == null){
    ymod = (value) => value;
  }
  if(x_data.length == y_data.length){
    stroke(col);
    line(xmod(x_data[0]),ymod(y_data[0]),xmod(x_data[1]),ymod(y_data[1]));
    for(let i = 1; i < x_data.length-1; i++){
      line(xmod(x_data[i]),ymod(y_data[i]),xmod(x_data[i+1]),ymod(y_data[i+1]));
    }
  }
  else{
    print("X and Y must have same length")
  }
}


let x_data = [];
let y_data = [];
let period = 260;
let steps = 4;
let amplitude = 360;
let nfunc_percent = 0.6;
let offset = 0;
let ssbt = [100,200,0,100];

let period_slider;
let steps_slider;
let amplitude_slider;
let nfunc_percent_slider;
let offset_slider;

let ratio_mult = 1;
let ratio_mult_input;
 

let func_sel;

let pause_box;

let count = 0;

function setup() {
  var myCanvas = createCanvas(windowWidth-200, windowHeight/2);
  myCanvas.parent("canvas");
  W = width;
  H = height;

  
  //Initial graph so it doesn't flash in on first frame
  for(let i = 0; i< 2*width; i++){
    x_data.push(i);
    y_data.push(func_stairs(easeOutBounce,i, period, steps, H/2, nfunc_percent, offset)+H/8);
  }
  
  
  
  
  
  
  
  //SLIDERS
  period_slider = createSlider(10, 3*W, period, 10);
  period_slider.input(update_graph);
  period_slider.parent(select("#PeriodSliderDiv"))
  
  steps_slider = createSlider(1, 36, steps, 1);
  steps_slider.input(update_graph);
  steps_slider.parent(select("#StepsSliderDiv"))

  amplitude_slider = createSlider(10, H-(H/8), H/2, 10);
  amplitude_slider.input(update_graph);
  amplitude_slider.parent("#AmplitudeSliderDiv")



  nfunc_percent_slider = createSlider(0.5, 0.99, nfunc_percent, 0.01);
  nfunc_percent_slider.input(update_graph);
  nfunc_percent_slider.parent("#FuncPercentSliderDiv");

  offset_slider = createSlider(0, 1, offset, 0.01);
  offset_slider.input(update_graph);
  offset_slider.parent("#OffsetSliderDiv");
  
  

  
  func_sel = createSelect();
  func_sel.option(easeOutBounce.name);
  func_sel.option(easeInBounce.name);
  func_sel.option(smooth_step.name);
  func_sel.option(easeInOutBounce.name);
  func_sel.option(easeOutElastic.name);
  func_sel.option(easeInOutElastic.name);
  func_sel.option(easeInOutBack.name);
  // func_sel.option(.name);
  // func_sel.option(.name);
  
  func_sel.selected(easeOutBounce);
  func_sel.changed(update_graph);
  func_sel.parent("#EasingFunctionDiv");
  
  ratio_mult_input = createInput('3');
  ratio_mult_input.input(update_graph);
  ratio_mult_input.parent("#SecondGearTeethDiv")
  
  pause_box = createCheckbox('Pause rotation', false);
  pause_box.style("color","gray");
  pause_box.parent("#PauseButtonDiv");
  
  
}

function draw() {
  background(20);

  
  push();
  scale(1,-1);
  translate(0, -H);
  graph(x_data,y_data,col = 255);
  pop();
  
  push();
  angleMode(DEGREES);
  

  if(!pause_box.checked()){
    count++;
  }
  
  
  //THIS IS THE ROTATION, IE WHAT IT WOULD LOOK LIKE IN YOUR THING
  let rotation_amount = func_stairs(window[func_sel.value()],count, period_slider.value(), steps_slider.value(), 360, nfunc_percent_slider.value(), 0)+offset_slider.value()*360;
  
    
  rectMode(RADIUS);
  let g1r = 50;
  let g1s = steps_slider.value();
  let g2s = Number(ratio_mult_input.value());
  let g1 = new Gear(g1r,g1s);
  let g2 = new Gear(g1r*(g2s/g1s),g2s);
  push();
  translate(W/2,H/2);
  rotation_amount = func_stairs(window[func_sel.value()],count, period_slider.value(), g1s, 360, nfunc_percent_slider.value(), 0)+offset_slider.value()*360;
  rotate(rotation_amount);
  g1.draw();
  pop();
  push();
  translate(W/2,H/2);
  translate(g1r+g1r*(g2s/g1s),0);
  rotation_amount = func_stairs(window[func_sel.value()],count, (period_slider.value()*g2s)/g1s, g2s, 360, nfunc_percent_slider.value(), 0)+offset_slider.value()*360;
  rotate(-rotation_amount);
  g2.draw(180);
  pop();

  pop();

  
  push();
  fill(255);
  text(`Period: ${period_slider.value()}`, 0, height - 3);
  text(`Steps : ${steps_slider.value()}`, 0, height - (3+15));
  text(`nfunc%: ${nfunc_percent_slider.value()}`, 0, height - (3+2*15));
  text(`rotation offset: ${(offset_slider.value()*360).toFixed(2)}`, 0, height - (3+3*15));
  pop();
  
}

function update_graph(){
  x_data = [];
  y_data = [];
  for(let i = 0; i< 2*width; i++){
    x_data.push(i);
    y_data.push((func_stairs(window[func_sel.value()],i, period_slider.value(), steps_slider.value(), amplitude_slider.value(), nfunc_percent_slider.value(), offset_slider.value()*period_slider.value())+H/8));
  } 
}

function windowResized() {
  resizeCanvas(windowWidth, windowHeight/2);
}


