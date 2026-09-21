// ================================
// 🎤 Voice + 🔊 Speaker + Chat JS
// ================================

// --- Global Variables ---
let recognizing = false;              // mic state
let recognition;                      // speech recognition instance
let synth = window.speechSynthesis;   // speech synthesis
let speaking = false;                 // speaker state
let lastReply = "";                   // store last bot reply
let voices = [];                     // store loaded voices

// --- Load Voices ---

function loadVoices() {
    voices = synth.getVoices();
    if (voices.length > 0) {
        console.log("✅ Voices loaded:", voices);
    }
}

// Listen for when voices are fully loaded
synth.onvoiceschanged = loadVoices;

// Call once in case voices already loaded
loadVoices();

// ✅ Ensure voices are loaded after a short delay
setTimeout(loadVoices, 100);
// --- Init Speech Recognition ---
if ("webkitSpeechRecognition" in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => {
        recognizing = true;
        document.querySelector(".mic-btn").classList.add("listening");
        console.log("🎤 Listening...");
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById("user-input").value = transcript;
        sendMessage(); // 👈 auto-send after speaking
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
    };

    recognition.onend = () => {
        recognizing = false;
        document.querySelector(".mic-btn").classList.remove("listening");
        console.log("🎤 Stopped listening.");
    };
} else {
    alert("❌ Your browser does not support Speech Recognition.");
}

// --- Mic Toggle ---
function toggleSpeak() {
    let btn = document.querySelector(".speak-btn");

    if (synth.speaking) {
        synth.cancel();
        btn.classList.remove("speaking");
        return;
    }

    if (!lastReply || lastReply.trim() === "") {
        alert("No reply to read!");
        return;
    }

    // Replace ₹numbers with words
    let textToSpeak = lastReply.replace(/\s*₹\s*(\d[\d,]*)/g, (match, p1) => {
        let num = parseInt(p1.replace(/,/g, '')); // remove commas
        if (!isNaN(num)) return "Rupees " + numberToWords(num);
        return match;
    });

    // Prepare speech
    let speech = new SpeechSynthesisUtterance(textToSpeak);

    // Select Tamil voice if Tamil detected
    let tamilDetected = /[\u0B80-\u0BFF]/.test(textToSpeak);
    if (tamilDetected) {
        speech.voice = voices.find(v => v.lang.startsWith("ta")) || voices[0];
    } else {
    speech.voice = voices.find(v => v.lang.startsWith("en")) || voices[0];
    }

    speech.rate = 1;
    btn.classList.add("speaking");

    speech.onend = () => btn.classList.remove("speaking");
    speech.onerror = () => btn.classList.remove("speaking");

    synth.speak(speech);

}



// Convert numbers to words (simple version)
function numberToWords(num) {
    const ones = ["","one","two","three","four","five","six","seven","eight","nine"];
    const teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"];
    const tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"];
    
    if (num < 10) return ones[num];
    if (num < 20) return teens[num-10];
    if (num < 100) return tens[Math.floor(num/10)] + (num%10 ? " " + ones[num%10] : "");
    if (num < 1000) return ones[Math.floor(num/100)] + " hundred" + (num%100 ? " " + numberToWords(num%100) : "");

    // Indian numbering system
    const units = [
        {value: 10000000, name: "crore"},
        {value: 100000, name: "lakh"},
        {value: 1000, name: "thousand"}
    ];

    for (let i = 0; i < units.length; i++) {
        if (num >= units[i].value) {
            let quotient = Math.floor(num / units[i].value);
            let remainder = num % units[i].value;
            return numberToWords(quotient) + " " + units[i].name + (remainder ? " " + numberToWords(remainder) : "");
        }
    }

    return numberToWords(Math.floor(num/100)) + " hundred" + (num%100 ? " " + numberToWords(num%100) : "");
}






// --- Send Message ---
async function sendMessage() {
    const input = document.getElementById("user-input");
    const chatWindow = document.getElementById("chat-box"); // ✅ match HTML ID
    const userMessage = input.value.trim();

    if (userMessage === "") return;

    // Show user message
    const userDiv = document.createElement("div");
    userDiv.className = "message user";
    userDiv.textContent = userMessage;
    chatWindow.appendChild(userDiv);

    // Show "Typing..." while waiting
    const botDiv = document.createElement("div");
    botDiv.className = "message bot";
    botDiv.textContent = "Typing...";
    chatWindow.appendChild(botDiv);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    try {
        // Send request to Flask backend
        const response = await fetch("http://127.0.0.1:5000/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userMessage })
        });

        const data = await response.json();

        // Format bot reply
        let formattedReply = data.reply
            .replace(/^Q:/m, "<strong>Your Query:</strong>")
            .replace(/^A:/m, "<strong>Our Answer:</strong>")
            .replace(/\n/g, "<br><br>")
            .replace(/\b(Overview|Btech|Bba|Mba|Bsc|Bcom)\b/gi, (match) => `<strong>${match}</strong>`);

        botDiv.innerHTML = formattedReply;

        // Save for speaker button
        // Save last reply for speaker
        lastReply = botDiv.textContent;

        // Convert numbers to words (simple version for thousands)


    } catch (error) {
        console.error("Error:", error);
        botDiv.textContent = "⚠️ Server error. Please try again later.";
    }

    // Scroll & clear input
    chatWindow.scrollTop = chatWindow.scrollHeight;
    input.value = "";
}

// --- Enter Key to Send ---
document.getElementById("user-input").addEventListener("keypress", function (event) {
    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }
});
// --- Exit Button Redirect ---
document.getElementById("exitBtn").addEventListener("click", function(event) {
    event.preventDefault(); // prevent default navigation
    // Stop microphone if active
    if (recognition && recognizing) recognition.stop();
    // Stop speech if active
    if (synth.speaking) synth.cancel();
    // Redirect to Flask home route
    window.location.href = "/";
});
