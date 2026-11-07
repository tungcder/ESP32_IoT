#include <Arduino.h>
#include "web_page.h"

const char webpage[] PROGMEM = R"rawliteral(

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

<title>ESP32 Robot Controller</title>


<style>

/* ================= GENERAL ================= */

* {

  box-sizing: border-box;

  user-select: none;

  -webkit-user-select: none;

  -webkit-touch-callout: none;

}


body {

  margin: 0;

  background:
    radial-gradient(circle at top, #1d2935, #080b0e 70%);

  color: white;

  font-family: Arial, sans-serif;

  text-align: center;

  min-height: 100vh;

  overflow-x: hidden;

  overflow-y: auto;

  touch-action: pan-y;

}


/* ================= HEADER ================= */

.header {

  padding-top: 25px;

}


.header h1 {

  margin: 0;

  font-size: 27px;

  letter-spacing: 1px;

}


.subtitle {

  margin-top: 6px;

  color: #777;

  font-size: 13px;

}


/* ================= STATUS ================= */

.status {

  display: inline-block;

  margin-top: 20px;

  padding: 10px 25px;

  border-radius: 30px;

  background: #151a1f;

  border: 1px solid #333;

  color: #00ff88;

  font-size: 15px;

  font-weight: bold;

  letter-spacing: 1px;

}


/* ================= CONTROLLER ================= */

.controller {

  width: 310px;

  max-width: 95vw;

  margin: 30px auto 0;

}


/* ================= BUTTON ================= */

.control-btn {

  width: 85px;

  height: 85px;

  margin: 6px;

  border: none;

  border-radius: 22px;

  background:
    linear-gradient(145deg, #252c33, #151a1f);

  color: white;

  font-size: 34px;

  font-weight: bold;

  box-shadow:

    0 7px 15px rgba(0,0,0,0.5),

    inset 0 1px 1px rgba(255,255,255,0.05);

  transition:
    transform 0.08s,
    background 0.08s;

  -webkit-tap-highlight-color: transparent;

  touch-action: none;

}


.control-btn.active {

  background: #00a86b;

  transform: scale(0.92);

  box-shadow:

    0 0 25px rgba(0,255,136,0.35);

}


/* ================= STOP ================= */

.stop {

  background:
    linear-gradient(145deg, #e63946, #a4161a);

  font-size: 28px;

}


.stop:active {

  transform: scale(0.92);

  background: #ff3030;

}


/* ================= LED SECTION ================= */

.led-section {

  margin-top: 20px;

  width: 320px;

  max-width: 95vw;

  margin-left: auto;

  margin-right: auto;

}


.led-title {

  color: #777;

  font-size: 13px;

  letter-spacing: 1px;

  margin-bottom: 12px;

}


/* ================= MODE BUTTONS ================= */

.mode-container {

  display: flex;

  justify-content: center;

  gap: 10px;

}


.mode-btn {

  width: 135px;

  height: 45px;

  border: none;

  border-radius: 14px;

  background: #151a1f;

  border: 1px solid #333;

  color: #aaa;

  font-size: 14px;

  font-weight: bold;

}


.mode-btn.active {

  background: #00a86b;

  color: white;

  border-color: #00a86b;

}


/* ================= ALL LED BUTTON ================= */

.all-led-btn {

  margin-top: 12px;

  width: 280px;

  height: 50px;

  border: none;

  border-radius: 15px;

  background:
    linear-gradient(145deg, #252c33, #151a1f);

  color: white;

  font-size: 16px;

  font-weight: bold;

}


.all-led-btn.on {

  background: #00a86b;

  box-shadow: 0 0 20px rgba(0,255,136,0.35);

}


/* ================= INFO ================= */

.info {

  margin-top: 15px;

  color: #777;

  font-size: 12px;

  line-height: 1.5;

}


/* ================= FOOTER ================= */

.footer {

  position: fixed;

  bottom: 10px;

  width: 100%;

  color: #444;

  font-size: 11px;

  letter-spacing: 1px;

}

</style>

</head>


<body>


<!-- ================= HEADER ================= -->

<div class="header">

  <h1>ESP32 ROBOT</h1>

  <div class="subtitle">

    WiFi Remote Controller

  </div>


  <div class="status" id="status">

    STOPPED

  </div>

</div>


<!-- ================= CONTROLLER ================= -->

<div class="controller">


  <!-- FORWARD -->

  <div>

    <button

      class="control-btn"

      id="forward">

      &#8593;

    </button>

  </div>


  <!-- LEFT / STOP / RIGHT -->

  <div>

    <button

      class="control-btn"

      id="left">

      &#8592;

    </button>


    <button

      class="control-btn stop"

      id="stop">

      &#9632;

    </button>


    <button

      class="control-btn"

      id="right">

      &#8594;

    </button>

  </div>


  <!-- BACKWARD -->

  <div>

    <button

      class="control-btn"

      id="backward">

      &#8595;

    </button>

  </div>


</div>



<!-- ================= DRIVING MODE ================= -->
<div class="led-section">
  <div class="led-title">DRIVING MODE</div>
  <div class="mode-container">
    <button class="mode-btn" id="driveAutoMode">OBSTACLE AUTO</button>
    <button class="mode-btn active" id="driveManualMode">WI-FI MANUAL</button>
  </div>
  <div class="info">AUTO: tránh vật cản bằng HC-SR04 + SG90<br>MANUAL: giữ nút mũi tên để điều khiển</div>
</div>

<!-- ================= LED CONTROL ================= -->

<div class="led-section">

  <div class="led-title">

    LED LIGHT CONTROL

  </div>


  <div class="mode-container">

    <button

      class="mode-btn active"

      id="autoMode">

      AUTO

    </button>


    <button

      class="mode-btn"

      id="manualMode">

      MANUAL

    </button>

  </div>


  <button

    class="all-led-btn"

    id="allLed">

    ALL LEDs OFF

  </button>

</div>


<div class="info">

  HOLD TO MOVE

  <br>

  AUTO: LEDs follow movement

  <br>

  MANUAL: Control all LEDs

</div>


<div class="footer">

  ESP32 WiFi Robot Controller

</div>


<script>


// ======================================================
// MOVEMENT VARIABLES
// ======================================================

let moveInterval = null;

let currentDirection = null;


// ======================================================
// DRIVING MODE (separate from LED mode)
// ======================================================
const driveAutoButton = document.getElementById("driveAutoMode");
const driveManualButton = document.getElementById("driveManualMode");

driveAutoButton.addEventListener("click", function() {
  stopMove(false);
  driveAutoButton.classList.add("active");
  driveManualButton.classList.remove("active");
  fetch("/driveauto").catch(() => {});
});

driveManualButton.addEventListener("click", function() {
  stopMove(false);
  driveManualButton.classList.add("active");
  driveAutoButton.classList.remove("active");
  fetch("/drivemanual").catch(() => {});
});

// ======================================================
// LED VARIABLES
// ======================================================

let currentLedMode = "auto";

let allLedState = false;


// ======================================================
// START MOVEMENT
// ======================================================

function startMove(direction) {

  if (currentDirection === direction) {

    return;

  }


  if (moveInterval !== null) {

    clearInterval(moveInterval);

    moveInterval = null;

  }


  currentDirection = direction;


  const button =
    document.getElementById(direction);

  button.classList.add("active");


  document.getElementById("status").innerHTML =

    direction.toUpperCase();


  fetch("/" + direction)

    .catch(() => {});


  moveInterval = setInterval(function() {

    fetch("/" + direction)

      .catch(() => {});

  }, 250);

}


// ======================================================
// STOP MOVEMENT
// ======================================================

function stopMove(sendStop = true, forceStop = false) {

  const wasMoving = currentDirection !== null;

  if (moveInterval !== null) {

    clearInterval(moveInterval);

    moveInterval = null;

  }


  if (currentDirection !== null) {

    const button =
      document.getElementById(currentDirection);

    button.classList.remove("active");

  }


  currentDirection = null;


  document.getElementById("status").innerHTML =

    "STOPPED";


  if (sendStop && (wasMoving || forceStop)) {

    fetch("/stop")

      .catch(() => {});

  }

}


// ======================================================
// BUTTON SETUP
// ======================================================

function setupButton(id, direction) {

  const button =
    document.getElementById(id);


  // ================= TOUCH =================

  button.addEventListener(

    "touchstart",

    function(event) {

      event.preventDefault();

      startMove(direction);

    },

    { passive: false }

  );


  button.addEventListener(

    "touchend",

    function(event) {

      event.preventDefault();

      stopMove();

    },

    { passive: false }

  );


  button.addEventListener(

    "touchcancel",

    function(event) {

      event.preventDefault();

      stopMove();

    },

    { passive: false }

  );


  // ================= MOUSE =================

  button.addEventListener(

    "mousedown",

    function(event) {

      event.preventDefault();

      startMove(direction);

    }

  );


  button.addEventListener(

    "mouseup",

    function(event) {

      event.preventDefault();

      stopMove();

    }

  );


  button.addEventListener(

    "mouseleave",

    function() {

      stopMove();

    }

  );

}


// ======================================================
// AUTO LED MODE
// ======================================================

document

  .getElementById("autoMode")

  .addEventListener("click", function() {

    currentLedMode = "auto";


    document

      .getElementById("autoMode")

      .classList.add("active");


    document

      .getElementById("manualMode")

      .classList.remove("active");


    fetch("/ledauto")

      .catch(() => {});

  });


// ======================================================
// MANUAL LED MODE
// ======================================================

document

  .getElementById("manualMode")

  .addEventListener("click", function() {

    currentLedMode = "manual";


    document

      .getElementById("manualMode")

      .classList.add("active");


    document

      .getElementById("autoMode")

      .classList.remove("active");


    fetch("/ledmanual")

      .catch(() => {});

  });


// ======================================================
// ALL LED BUTTON
// ======================================================

document

  .getElementById("allLed")

  .addEventListener("click", function() {


    if (currentLedMode !== "manual") {

      return;

    }


    allLedState = !allLedState;


    const button =
      document.getElementById("allLed");


    if (allLedState) {

      button.innerHTML = "ALL LEDs ON";

      button.classList.add("on");


      fetch("/ledon")

        .catch(() => {});

    }

    else {

      button.innerHTML = "ALL LEDs OFF";

      button.classList.remove("on");


      fetch("/ledoff")

        .catch(() => {});

    }

  });


// ======================================================
// CREATE MOVEMENT BUTTONS
// ======================================================

setupButton("forward", "forward");

setupButton("backward", "backward");

setupButton("left", "left");

setupButton("right", "right");


// ======================================================
// STOP BUTTON
// ======================================================

document

  .getElementById("stop")

  .addEventListener(

    "click",

    function() {

      stopMove(true, true);

    }

  );


// ======================================================
// BROWSER SAFETY
// ======================================================

window.addEventListener(

  "blur",

  function() {

    stopMove();

  }

);


</script>

</body>

</html>
\n)rawliteral";
